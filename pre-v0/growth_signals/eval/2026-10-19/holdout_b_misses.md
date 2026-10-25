# Held-out B (older BV/WING sitemap articles): misses for the NEXT round (not tuned this round)

False negatives
- WING H1 market_expansion: "45 net openings" / "135 net openings" (rule needs "net new openings").
- WING H3 market_expansion: "build-out of 80 additional restaurants", "will open its first location in France" (base-form "open" was removed after the CSG "open APIs" false positive; needs an object-adjacent form).
- WING H3 new_contract: "Extend Development Agreement" / "expands the current development agreement and extends it" (present tense extend/expand).
- WING H6 new_contract: "exclusive delivery partner" (quote by DoorDash); product_launch: "new side-order menu items", "New Sides Now Available".
- WING H10 product_launch: "Wingstop's new Hot Honey Rub" (possessive + new + named item).
- BV H1 acquisition: "today announced the acquisition of Green Image"; title "Green Image, LLC Acquired by BrightView" (passive with the company as acquirer is excluded today).
- BV H5 hiring: "investments made in our expanded sales teams" (adjective form + plural).
- BV H6 product_launch: "has upgraded BrightView Connect", "Released earlier this year", "The new BrightView Connect is ...".
- BV H8 new_contract: "has been selected by ... Country Club to maintain" (selected needs provider/partner/platform).
- BV H10 new_contract: "named Major League Baseball's Official Field Consultant".
- BV H11 credit_positive: "completed a repricing of its ... term loan" (repricing not covered).
- BV H13 new_contract: "Secured new golf course maintenance contracts" (BUG: \bcontract\b does not match plural "contracts").

False positives
- WING H12 product_launch: About block history "In February 2019, the Company launched its new tagline" (old fact in own About block; tagline is not a product).
- WING H9 product_launch: "Announces Pricing of Secondary Offering" (securities "offering" matched the pass/card/program/offering alternative).
- BV H12 new_contract: "entered into an agreement to repurchase ... shares" (add share repurchase to contract exclusions).
- BV H3 market_expansion: acquired firm's president quoted: "we will be able to expand West Bay's standard ... within our market" (quote by another company's executive; actor check only reads the words before the verb).
