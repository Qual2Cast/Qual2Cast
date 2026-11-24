"""Economic traits and tags: one yes/no/unknown answer per question per company (v2, decided 2026-11-24).

Two kinds of question, asked in the same call:

- Tags (T1-T4) say what kind of company it is: products and/or services, consumers and/or organizations. They are
  only used to cut the analysis into subgroups (for example "does recurring revenue matter more among services
  targets?"). A tag is never a matching facet and never a treatment.
- Traits (E1-E6) are economic characteristics every company has, whatever its type: recurring revenue, cyclical
  demand, big-ticket sales, people-delivered, large customers, asset-heavy. Each is a treatment in the X-learner
  (09_analysis): a pair matches on a trait when both companies give the same yes/no answer.

Rules (EVAL_METHOD.md):
- Every company answers every question. "unknown" when neither the model's knowledge nor the page text settles
  it; unknown is never a mismatch. There is no "not applicable": the questions are written to apply to any company.
- A company with several businesses answers for the larger part (a mostly-equipment maker with some consumables
  answers no to recurring revenue); the reason names the other part.
- Software (licences, SaaS) is a product; implementation and managed IT are services.
- The buyer is whoever chooses and receives the purchase, not who pays (a patient is a consumer even when an
  insurer pays). A brand sold through retailers sells to consumers (the shopper chooses the brand) and to
  organizations (the retailer buys it).
- No financial figures in the answer.

The traits are on the test list, never on the rubric's definition list (product, customers, revenue model, chain
step): a trait is what we test against people's peer judgments, so it must not be part of the definition of peer.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

PROMPT_VERSION = "2026-11-24a"
MAX_PAGE_WORDS = 1500        # saved website text sent per company (figures already removed by the scrape filters)
ANSWERS = ("yes", "no", "unknown")


@dataclass(frozen=True)
class Question:
    id: str          # T1 ... E6
    name: str        # column name
    kind: str        # "tag" or "trait"
    question: str
    yes: str         # examples of yes
    no: str          # examples of no
    rule: str = ""   # how to decide in the hard cases


QUESTIONS = [
    Question("T1", "offers_products", "tag",
             "Are products one of the company's main offerings?",
             "manufactured goods, equipment, food, chemicals, homes it builds and sells, software licences or SaaS",
             "only incidental products, such as parts used inside a repair job or a cafe inside a hospital",
             "Software counts as a product. 'Main' means named among its main offerings, not a side line."),
    Question("T2", "offers_services", "tag",
             "Are services, meaning work done for customers, one of the company's main offerings?",
             "care, repair, installation, transport, staffing, construction, engineering, insurance, banking, "
             "operating assets for others, implementation or managed IT",
             "only warranty or support that comes with a product it sells",
             "Banks, insurers, REITs and utilities count as services."),
    Question("T3", "sells_to_consumers", "tag",
             "Are individual people or households among its main buyers?",
             "restaurants, homebuilders, hospitals and clinics (patients), schools (students), consumer brands sold "
             "through stores",
             "sells only to businesses, institutions or government",
             "The buyer is whoever chooses and receives the purchase, not who pays. A brand sold through retailers "
             "is yes: the shopper chooses the brand."),
    Question("T4", "sells_to_organizations", "tag",
             "Are businesses, institutions or government agencies among its main buyers?",
             "contractors, manufacturers, hospitals buying devices, utilities buying equipment, retailers buying a "
             "brand's goods for resale, government agencies",
             "sells only to individual people or households",
             "A retailer buying goods to resell counts as an organization buyer."),
    Question("E1", "recurring_revenue", "trait",
             "Does most of its revenue come from customers who keep buying on an ongoing basis, rather than from "
             "one-off sales or projects?",
             "repeat orders of consumables, food, fuel, parts or supplies; subscriptions; multi-year service "
             "contracts; insurance policies; bank accounts; leases; utility service",
             "machinery, vehicles or homes bought once every few years; construction projects; one-time "
             "transactions or jobs",
             "Judge by the larger part of revenue. Repeat buying by the same customers counts even without a "
             "contract."),
    Question("E2", "cyclical_demand", "trait",
             "Can its customers easily postpone or cut these purchases when the economy turns down?",
             "dining out, travel, remodelling, boats, cars, machinery, new buildings, advertising, hiring-driven "
             "staffing",
             "groceries, utilities, medical care, maintenance and repair, insurance, regulated testing, "
             "government-mandated services",
             "Think of what this company's customers would do in a recession, not the economy as a whole."),
    Question("E3", "big_ticket", "trait",
             "Is a typical sale large and infrequent for the buyer, rather than small and frequent?",
             "homes, cars, boats, furniture, machinery, building projects, enterprise systems",
             "meals, groceries, supplies, parts, routine services, small software subscriptions",
             "Large relative to what that buyer usually spends, not in absolute dollars."),
    Question("E4", "people_delivered", "trait",
             "Is what customers pay for mainly the time and skill of the company's own staff, rather than goods "
             "or its technology, network or assets?",
             "staffing, nursing and home care, physician groups, engineering and consulting, field service, "
             "education",
             "manufacturers, distributors and retailers of goods; software; pipelines, utilities, payment networks; "
             "trucking fleets and other asset-based services",
             "Ask what would stop the service if the staff walked out tomorrow. A product company is no."),
    Question("E5", "large_customers", "trait",
             "Are its main customers large enterprises or government agencies, rather than small businesses or "
             "households?",
             "defense contractors, enterprise software, suppliers to automakers or big utilities, government IT",
             "consumer businesses, suppliers to small contractors or independent shops, small-business software",
             "A company selling to households is no."),
    Question("E6", "asset_heavy", "trait",
             "Does it need heavy, ongoing investment in plants, fleets, networks or properties to run and grow?",
             "utilities, pipelines, railroads, trucking fleets, airlines, hospitals, heavy manufacturing, REITs, "
             "rental fleets",
             "software, staffing, consulting, brokers, asset-light franchisors, distributors renting their "
             "warehouses",
             "Judge from what the business physically needs to grow, not from financial figures."),
]
QUESTION_NAMES = [q.name for q in QUESTIONS]
TAGS = [q.name for q in QUESTIONS if q.kind == "tag"]
TRAITS = [q.name for q in QUESTIONS if q.kind == "trait"]
BY_NAME = {q.name: q for q in QUESTIONS}

# Round 2 (decided 2026-11-24, after round 1's X-learner run): cyclical demand split true direct peers as often as
# non-peers, and its reasons showed the two facts that actually decided it: new builds vs maintenance of an
# installed base, and who ultimately pays (public budgets vs private buyers). Those two replace it, plus two PE value
# drivers. Asked in a separate call with its own prompt version; round 1's questions, prompt and table are unchanged.
PROMPT_VERSION_R2 = "2026-11-24b"
ROUND_2 = [
    Question("E7", "maintenance_led", "trait",
             "Does most of its revenue come from repairing, servicing, maintaining or replacing things customers "
             "already have installed or own, rather than from new builds, new installations or first-time purchases?",
             "aftermarket parts, repair and maintenance services, inspection and testing, reroofing and other "
             "replacement work, fleet servicing, maintenance and repair supplies",
             "new construction, new equipment sales, new installations, first-time product purchases, new software "
             "licences, consumables used up in normal operation (food, fuel, chemicals)",
             "Judge by the larger part of revenue. Consumables that are simply used up are no; parts and services "
             "that keep an existing installed base running are yes."),
    Question("E8", "publicly_funded", "trait",
             "Is most of its revenue ultimately paid by government, even when a contractor, insurer or provider sits "
             "in between?",
             "public road and infrastructure work, defense contracting, care paid by Medicare or Medicaid (including "
             "Medicare Advantage and managed Medicaid), public school services, government IT",
             "revenue paid by private businesses, consumers, employers or commercial insurers",
             "Count the final payer, not the immediate customer. A regulated utility billing households is no; a "
             "contractor building roads for a state agency is yes."),
    Question("E9", "serial_acquirer", "trait",
             "Does the company grow mainly by buying other companies, acquiring regularly as a roll-up or platform, "
             "rather than mainly by growing its own business?",
             "insurance brokerages, distribution and services roll-ups, software platforms that buy many small "
             "vendors, dental, veterinary or physician practice groups",
             "companies that grow mainly by selling more, opening their own sites or launching products, with only "
             "occasional acquisitions",
             "One or two large deals do not make a serial acquirer; a steady stream of acquisitions as the main way "
             "it grows does."),
    Question("E10", "mission_critical", "trait",
             "Would customers face real cost, risk or disruption if they switched away from this company, rather "
             "than being able to change suppliers easily?",
             "core business software, components qualified into a customer's own product, safety- or "
             "regulation-critical services, utilities, payment processing, outsourced payroll",
             "commodity products, restaurants and retail, staffing, freight brokerage, standard supplies bought on "
             "price, advertising",
             "Ask how hard it is for a typical customer to switch: retraining, re-qualification, regulatory approval "
             "or downtime mean yes; a call to another supplier means no."),
]
ROUND_2_NAMES = [q.name for q in ROUND_2]
BY_NAME.update({q.name: q for q in ROUND_2})
NUMBER_WORDS = {4: "four", 10: "ten"}


def question_guide(questions: list[Question] | None = None) -> str:
    blocks = []
    for q in (questions or QUESTIONS):
        lines = [f"{q.id} {q.name}: {q.question}", f"Yes, for example: {q.yes}.", f"No, for example: {q.no}."]
        if q.rule:
            lines.append(q.rule)
        blocks.append("\n  ".join(lines))
    return "\n\n".join(blocks)


def instructions(questions: list[Question] | None = None) -> str:
    """The prompt's instructions for one question set (round 1 by default; its text is unchanged since 2026-11-24a)."""
    questions = questions or QUESTIONS
    return f"""\
You describe a company for a research project that compares companies' business models. Answer \
{NUMBER_WORDS.get(len(questions), str(len(questions)))} yes/no questions about it.

First, say whether you know this company: set "knows_company" to true only if you recognize this specific \
company from what you already know. A name and a web address alone are not knowing it; do not guess from the \
name, the web address or what is typical for similarly named companies. If you don't know it, use only the \
website text below; if that text doesn't settle a question, answer "unknown".

For each question answer "yes", "no" or "unknown", and give a reason of at most twenty words that names the \
products, services or customers that decided it. Answer "unknown" only when you really cannot tell; do not \
make up facts.

Describe the company as it is now. Leave out businesses it has sold, spun off or closed. If the company runs \
several businesses, answer for the larger part of the business and name the other part in the reason.

The buyer is whoever chooses and receives the purchase, not who pays for it. Software counts as a product.

Do not give financial information: no revenue, profit, market value, share price, stock ticker or employee \
counts.

Everything you need is in this message. Do not run commands, open files or search the web. Write the JSON on \
one line.

Questions:

{question_guide(questions)}

Also write "notes": leave it empty unless something important is uncertain; then say what in one short sentence.
"""


INSTRUCTIONS = instructions(QUESTIONS)
INSTRUCTIONS_R2 = instructions(ROUND_2)
ROUNDS = {1: (QUESTIONS, PROMPT_VERSION, INSTRUCTIONS), 2: (ROUND_2, PROMPT_VERSION_R2, INSTRUCTIONS_R2)}


def answer_schema(questions: list[Question] | None = None) -> dict:
    names = [q.name for q in (questions or QUESTIONS)]
    item = {"type": "object", "additionalProperties": False, "required": ["answer", "reason"],
            "properties": {"answer": {"type": "string", "enum": list(ANSWERS)}, "reason": {"type": "string"}}}
    return {"type": "object", "additionalProperties": False,
            "required": ["knows_company", *names, "notes"],
            "properties": {"knows_company": {"type": "boolean"}, **{n: item for n in names},
                           "notes": {"type": "string"}}}


def page_text(lines: dict[str, str], max_words: int = MAX_PAGE_WORDS) -> str:
    """The saved website lines (label -> line, from facets.build_prompt) as plain text, up to max_words."""
    out, budget = [], max_words
    for line in lines.values():
        words = line.split()
        if budget <= 0:
            break
        out.append(line if len(words) <= budget else " ".join(words[:budget]))
        budget -= len(words)
    return "\n".join(out)


def build_prompt(company_name: str, website: str, pages: str, round: int = 1) -> str:
    body = f"Company: {company_name}\nWebsite: {website}"
    if pages:
        body += f"\n\nText from the company's website:\n{pages}"
    return ROUNDS[round][2] + "\n" + body


def fingerprint(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()


FIGURE = re.compile(r"\$\s?\d|\d[\d,.]*\s?(?:million|billion|bn|mm|%)", re.I)


def check_answer(raw: dict, had_pages: bool, questions: list[Question] | None = None) -> tuple[dict, list[str]]:
    """Validate one answer. Returns ({name: {"answer", "reason"}}, issues). A company the model doesn't know and
    that had no page text gets every answer unknown, whatever the model wrote."""
    names = [q.name for q in (questions or QUESTIONS)]
    missing = [n for n in names if n not in raw]
    if missing:
        raise ValueError(f"answer lacks {missing}")
    issues, answers = [], {}
    forced_unknown = not raw.get("knows_company") and not had_pages
    if forced_unknown:
        issues.append("company_not_known_no_pages")
    for n in names:
        a = raw[n]
        answer = str(a.get("answer", "")).strip().lower()
        if answer not in ANSWERS:
            raise ValueError(f"{n}: answer {answer!r} not in {ANSWERS}")
        reason = str(a.get("reason", "")).strip()
        if forced_unknown:
            answer = "unknown"
        if FIGURE.search(reason):
            issues.append(f"figure_in_reason:{n}")
        answers[n] = {"answer": answer, "reason": reason}
    return answers, issues


def table_row(answers: dict, questions: list[Question] | None = None) -> dict:
    row = {}
    for n in [q.name for q in (questions or QUESTIONS)]:
        a = answers.get(n, {})
        row[n] = a.get("answer", "")
        row[f"{n}_reason"] = a.get("reason", "")
    return row


def schema_json() -> str:
    return json.dumps(answer_schema())
