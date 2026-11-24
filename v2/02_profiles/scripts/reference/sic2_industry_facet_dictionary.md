# SIC2 - 83 Industry Facet Dictionary

## Selecting facets for multiple business segments

- Identify each disclosed segment and distinguish business activities from geographic reporting divisions. Different regions may use the same industry module.
- Select modules from each segment’s actual products, services, customers and revenue model—not the company’s primary SIC alone. One segment may need multiple modules; several segments may share one. Mark inferred mappings explicitly.
- Fill applicable general and industry facets at segment level. Use `Not applicable` for confirmed non-applicability and `Unknown` for missing evidence. Do not copy company-wide facts into every segment or count the same fact twice in scoring.
- Retain segment names, source excerpts, links and dates. Owning operational property alone does not establish a separate real-estate business.
- For pseudo-private targets, identify segments and select modules using only permitted official business-website information; do not use hidden SEC/vendor information to guide matching.

## A. Agriculture, Forestry and Fishing

### SIC 01 — Agricultural Production — Crops

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-01)

| Industry-Specific Facets             | Example Extracted Text / Value                                                                  |
| ------------------------------------ | ----------------------------------------------------------------------------------------------- |
| Crop / cultivation category          | • Corn and soybeans • Apples and citrus • Greenhouse vegetables                                 |
| Land area by use and tenure          | • 25,000 cultivated acres • 12,000 irrigated acres • 8,000 leased acres                         |
| Crop-specific yield                  | • Corn: 180 bushels/acre • Wheat: 3.2 metric tonnes/hectare                                     |
| Crop calendar                        | • Single annual crop • Winter wheat–summer soybean rotation • Controlled-environment production |
| Irrigation system / water dependence | • Rain-fed fields • Center-pivot irrigation • Drip-irrigated orchards                           |
| Crop price realization / hedging     | • Spot-linked grain sales • Forward-priced harvest contracts • Commodity futures hedges         |
| Harvest frequency                    | • One grain harvest/year • Two vegetable crops/year • Weekly greenhouse picking                 |
| Land / water constraints             | • Irrigation-water allocation • Leased-land renewals • Drought-affected acreage                 |

### SIC 02 — Agricultural Production — Livestock and Animal Specialties

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-02)

Apply animal and aquaculture rows to the actual production business. SIC 0273 covers animal aquaculture; SIC 09 separately contains fish hatcheries/preserves and species-specific fisheries. Verify the detailed activity before mapping an aquatic operation. Processing-only establishments require a separate manufacturing classification. [Scope: major group 02](https://www.osha.gov/data/sic-manual/major-group-02).

| Industry-Specific Facets             | Example Extracted Text / Value                                                                               |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| Animal / production category         | • Beef cattle • Dairy cattle • Broilers and laying hens                                                      |
| Animal inventory / output scale      | • 12,000 cattle on feed • 4,500 milking cows • 30,000 breeding sows                                          |
| Production / finishing cycle         | • Broilers marketed at 6–8 weeks • Cattle finished to target liveweight • Daily milk production              |
| Feed ration / input exposure         | • Corn–soybean meal ration • Purchased forage • Feed-grain hedging                                           |
| Breeding / grower arrangement        | • Owned breeding herd • Purchased feeder cattle • Contract poultry growers                                   |
| Processing integration               | • Live-animal sales to processors • Owned dairy processing business • Integrated poultry processing business |
| Biosecurity / animal health          | • Vaccination program • Herd disease surveillance • Restricted farm access                                   |
| Aquaculture system [0273]            | • Freshwater fish ponds • Recirculating aquaculture systems • Marine finfish cages                           |
| Aquaculture operating drivers [0273] | • Feed-conversion ratio: 1.4 kg/kg • Harvest survival: 90% • 12-month grow-out cycle                         |

### SIC 07 — Agricultural Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-07)

This group is broader than farm-field services: it also includes veterinary, animal-specialty and landscape services. Select the relevant service rows rather than assuming every client is a crop farm. [Scope](https://www.osha.gov/data/sic-manual/major-group-07).

| Industry-Specific Facets                | Example Extracted Text / Value                                                            |
| --------------------------------------- | ----------------------------------------------------------------------------------------- |
| Agricultural / animal service specialty | • Crop spraying • Livestock veterinary care • Landscape maintenance                       |
| Service equipment / crew model          | • Custom-harvesting combines • Mobile veterinary teams • Landscaping crews                |
| Seasonal workload                       | • Spring planting peak • Autumn harvest peak • Recurring lawn-care rounds                 |
| Service charging / contract basis       | • Fee per sprayed acre • Fee per veterinary visit • Seasonal grounds-maintenance contract |
| Customer operating scale                | • 2,000-acre grain farms • Commercial dairy herds • Municipal landscaping portfolios      |

### SIC 08 — Forestry

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-08)

Forestry includes timber tracts, forest nurseries/products and forestry services. Logging contractors that cut timber are SIC 2411, not automatically SIC 08. [Logging boundary](https://www.osha.gov/sic-manual/2411).

| Industry-Specific Facets               | Example Extracted Text / Value                                                       |
| -------------------------------------- | ------------------------------------------------------------------------------------ |
| Tree / forest-product species          | • Southern pine • Eucalyptus • Mixed hardwoods                                       |
| Timberland ownership / management role | • Owned timber tracts • Third-party forest management • Forest nursery operator      |
| Silvicultural / rotation cycle         | • 25-year pine rotation • 7-year eucalyptus rotation • Selective hardwood harvesting |
| Timberland area                        | • 150,000 productive acres • 40,000 hectares under management                        |
| Regeneration / forest stewardship      | • Replanting after harvest • Assisted natural regeneration • Selective thinning      |
| Forest health / climate exposure       | • Wildfire-prone tracts • Pest-management program • Drought-related growth reduction |

### SIC 09 — Fishing, Hunting & Trapping

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-09)

Commercial capture fishing, hatcheries/preserves, and hunting/trapping are separate activities within this group. Do not use farmed salmon as a default SIC 09 example, or assume every managed shellfish/hatchery business belongs to 0273. Species and operating activity determine the detailed route. [Scope](https://www.osha.gov/data/sic-manual/major-group-09); [aquaculture code listing](https://www.bls.gov/cew/classifications/industry/sic-industry-titles.htm).

| Industry-Specific Facets                     | Example Extracted Text / Value                                                                                       |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Species / aquatic-resource focus             | • Wild cod • Herring • Oysters and other shellfish                                                                   |
| Capture / harvest method                     | • Longline fishing • Trawling • Pot and trap fishing                                                                 |
| Fishing rights / quota basis                 | • Individual transferable quota • Annual total-allowable-catch allocation • Licensed fishing days                    |
| Capture / hatchery / managed-resource model  | • Wild commercial catch • Fish hatchery and stocking activity • Managed shellfish resource                           |
| Fishing fleet / effort scale                 | • Eight licensed trawlers • 400 vessel fishing-days/year • 20,000 gross tonnes of fleet capacity                     |
| Catch handling / landing route               | • Frozen-at-sea catch • Fresh landings at port • Onboard primary processing                                          |
| Hunting / trapping permissions               | • Species-specific hunting permits • Seasonal bag limits • Managed preserve access                                   |
| Hatchery / preserve operating drivers [0921] | • Five million juvenile fish released/year • Species-specific hatchery capacity • Stocking agreements with fisheries |

## B. Mining

### SIC 10 — Metal Mining

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-10)

Separate mineral resources from economically mineable reserves; neither is interchangeable with throughput or remaining mine life. Grade, recovery and costs must retain commodity-specific units and the issuer’s reporting definition. [SEC mining-disclosure guide](https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/modernization-property-disclosures-mining-registrants-small-entity-compliance-guide).

| Industry-Specific Facets          | Example Extracted Text / Value                                                         |
| --------------------------------- | -------------------------------------------------------------------------------------- |
| Metal / commodity mix             | • Copper–gold mine • Iron ore • Nickel–cobalt operation                                |
| Reserve / resource classification | • Proven and probable reserves • Measured and indicated resources • Inferred resources |
| Ore grade by commodity            | • 0.6% copper • 1.8 g/t gold • 62% iron content                                        |
| Remaining mine life               | • 18 years of reserve-supported production • 12-year approved mine plan                |
| Mining method / mine stage        | • Operating open pit • Underground stoping • Development-stage project                 |
| Metallurgical recovery            | • 88% copper recovery • 92% gold recovery                                              |
| Ore-processing capacity           | • 45,000 metric tonnes/day • 12 million metric tonnes/year                             |
| Mining cost / reporting basis     | • Copper C1 cash cost: $1.60/lb • Gold AISC: $1,250/oz                                 |

### SIC 12 — Coal Mining

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-12)

| Industry-Specific Facets           | Example Extracted Text / Value                                              |
| ---------------------------------- | --------------------------------------------------------------------------- |
| Coal quality                       | • High-volatile metallurgical coal • Low-sulfur thermal coal • Anthracite   |
| Mining method                      | • Underground longwall • Room-and-pillar mining • Surface strip mining      |
| Reserve-supported life             | • 12 remaining production years • 20-year mine plan                         |
| Thermal / metallurgical exposure   | • 80% metallurgical coal sales • Thermal coal for power generation          |
| Transport / export access          | • Rail-linked export terminal • Barge access • Truck-only domestic delivery |
| Product specification / wash yield | • 6,000 kcal/kg thermal coal • 8% ash content • 70% coal-preparation yield  |

### SIC 13 — Oil & Gas Extraction

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-13)

E&P and oilfield-service contractors share this broad major group but need different rows. Reserve/production fields apply to resource-owning operations; day rates and fleet utilization apply to service operations. Natural-gas pipeline activities can instead route to SIC 49. [Scope](https://www.osha.gov/data/sic-manual/major-group-13).

| Industry-Specific Facets                   | Example Extracted Text / Value                                                                             |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| Operating activity                         | • Crude-oil E&P • Natural-gas production • Contract drilling and field services                            |
| Production mix [E&P]                       | • 65% oil by boe • Gas-weighted production • NGL-rich production                                           |
| Basin / field exposure [E&P]               | • Permian Basin • Gulf of Mexico offshore • Appalachian gas basin                                          |
| Reserve measure / life [E&P]               | • Proved developed producing reserves • Proved undeveloped reserves • 10-year reserves-to-production ratio |
| Well / field decline [E&P]                 | • 25% first-year well decline • 8% mature-field annual decline                                             |
| Development intensity [E&P]                | • 40 wells drilled/year • 25 completed wells/year • Offshore tie-back development                          |
| Production cost / price basis [E&P]        | • Lifting cost: $12/boe • Brent-linked realized oil prices • Henry Hub-linked gas sales                    |
| Service line / fleet [oilfield services]   | • Land drilling rigs • Pressure-pumping fleets • Well-maintenance crews                                    |
| Contract / utilization [oilfield services] | • $25,000 rig day rate • 80% marketed-rig utilization • Multiwell service agreement                        |

### SIC 14 — Nonmetallic Minerals, Except Fuels

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-14)

| Industry-Specific Facets        | Example Extracted Text / Value                                                                            |
| ------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Mineral / product               | • Construction aggregates • Industrial sand • Salt                                                        |
| Extraction route                | • Surface quarry • Underground salt mine • Dredged sand                                                   |
| Reserves / remaining life       | • 30 years of quarry reserves • 20-year permitted extraction plan                                         |
| Beneficiation / processing      | • Crushing and screening • Washing and sizing • Drying and milling                                        |
| Delivery radius / logistics     | • 80-mile aggregate delivery radius • Rail-served industrial-mineral customers • Seaborne mineral exports |
| Product specification / permits | • Concrete-grade aggregates • High-purity silica • Permitted quarry expansion                             |

## C. Construction

### SIC 15 — Building Construction Contractors and Operative Builders

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-15)

| Industry-Specific Facets                       | Example Extracted Text / Value                                                           |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Building-market mix                            | • Single-family homes • Multifamily buildings • Commercial buildings                     |
| Project / building type                        | • Logistics warehouses • Office fit-outs • Residential subdivisions                      |
| Contracted backlog                             | • $600 million at year-end • 18 months of signed project work                            |
| Contract pricing / risk                        | • Guaranteed maximum price • Fixed-price construction contract • Cost-plus fee           |
| Self-perform / subcontract scope               | • Structural work self-performed • Mechanical and electrical work subcontracted          |
| Builder / contractor role                      | • Fee-based general contractor • Land-owning operative builder • Design–build contractor |
| Land / inventory exposure [operative builders] | • Owned finished lots • Optioned land parcels • Speculative homes under construction     |

### SIC 16 — Heavy Construction

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-16)

| Industry-Specific Facets            | Example Extracted Text / Value                                                                    |
| ----------------------------------- | ------------------------------------------------------------------------------------------------- |
| Infrastructure project type         | • Highway bridges • Water-treatment plants • Marine terminals                                     |
| Public / private client mix         | • State transportation projects • Municipal utility contracts • Private industrial projects       |
| Contracted backlog                  | • $1.2 billion at quarter-end • 24 months of signed work                                          |
| Heavy-equipment model               | • Owned excavation fleet • Leased specialist cranes • Subcontracted tunneling equipment           |
| Project delivery duration           | • Two-year bridge contract • Five-year rail program                                               |
| Fixed-price / cost-overrun exposure | • 60% of backlog fixed-price • Cost-plus reimbursable work • Price-escalation clauses             |
| Concession / operating commitments  | • Build-only contract • Design–build–operate contract • Long-term availability-payment concession |

### SIC 17 — Special Trade Contractors

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-17)

| Industry-Specific Facets                 | Example Extracted Text / Value                                                           |
| ---------------------------------------- | ---------------------------------------------------------------------------------------- |
| Specialist trade                         | • Electrical installation • Plumbing and HVAC • Roofing                                  |
| New-build / service mix                  | • 70% new construction revenue • Retrofit-led work • Recurring maintenance work          |
| Trade licenses / workforce qualification | • Licensed electricians • Certified welders • HVAC technician credentials                |
| Typical contract / job size              | • $2 million electrical contract • $15,000 replacement-system job                        |
| Maintenance / emergency recurrence       | • Annual HVAC service agreement • Emergency call-out repairs • Warranty-period servicing |

## D. Manufacturing

### SIC 20 — Food & Kindred Products

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-20)

| Industry-Specific Facets            | Example Extracted Text / Value                                                                   |
| ----------------------------------- | ------------------------------------------------------------------------------------------------ |
| Food / beverage category            | • Frozen potato products • Packaged bakery products • Nonalcoholic beverages                     |
| Brand / private-label manufacturing | • Owned consumer brands • Retailer private-label production • Foodservice contract manufacturing |
| Shelf life / storage condition      | • Seven-day chilled shelf life • 18-month frozen shelf life • Shelf-stable dry goods             |
| Processing technology               | • Freezing and packaging • Fermentation • UHT treatment                                          |
| Temperature-controlled logistics    | • Chilled production and distribution • Frozen warehousing • Ambient distribution                |
| Customer-channel sales mix          | • 80% foodservice sales • 60% grocery retail sales • Ingredient sales to manufacturers           |
| Input / food-safety exposure        | • Milk-price pass-through • Wheat procurement contracts • Allergen-segregated production         |

### SIC 21 — Tobacco Products

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-21)

Tobacco marketing authorization is not FDA product approval or a statement of safety. Preserve the market, product and regulatory pathway; do not map every modern nicotine product to SIC 21 from its name alone. [FDA terminology](https://www.fda.gov/consumers/consumer-updates/it-really-fda-approved).

| Industry-Specific Facets                 | Example Extracted Text / Value                                                                              |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Tobacco product / manufacturing role     | • Cigarette manufacturing • Cigar manufacturing • Tobacco stemming and redrying                             |
| Excise-tax / jurisdiction exposure       | • U.S. federal tobacco excise tax • State cigarette excise taxes • Export-market duties                     |
| Tobacco / nicotine format                | • Combustible tobacco • Chewing tobacco • Snuff                                                             |
| Distribution restrictions                | • Age-verified retail channels • Licensed wholesale distribution • Market-specific advertising restrictions |
| Marketing authorization / product status | • FDA tobacco marketing authorization • Pending PMTA • Marketed legacy tobacco product                      |

### SIC 22 — Textile Mill Products

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-22)

| Industry-Specific Facets        | Example Extracted Text / Value                                                       |
| ------------------------------- | ------------------------------------------------------------------------------------ |
| Fiber composition               | • Cotton–polyester blend • Wool • Nylon                                              |
| Fabric construction             | • Woven fabric • Knitted fabric • Nonwoven textile                                   |
| Textile production stages       | • Spinning and weaving • Dyeing and finishing • Integrated yarn-to-fabric production |
| Mill output capacity            | • 30 million linear yards/year • 20,000 metric tonnes of yarn/year                   |
| Fiber / chemical input exposure | • Cotton procurement prices • Polyester feedstock prices • Dye and chemical costs    |
| Textile end use                 | • Automotive upholstery • Industrial filtration • Apparel fabric                     |

### SIC 23 — Apparel & Finished Textile Products

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-23)

| Industry-Specific Facets         | Example Extracted Text / Value                                                                    |
| -------------------------------- | ------------------------------------------------------------------------------------------------- |
| Apparel / sewn-product category  | • Athletic wear • Workwear • Household textile goods                                              |
| Design / fashion cadence         | • Two seasonal collections/year • Weekly replenishment basics • Short-run fashion drops           |
| Manufacturing arrangement        | • Company-operated sewing factories • Contract cut-and-sew production • Outsourced finished goods |
| Inventory / order seasonality    | • Back-to-school order peak • Holiday production build • Year-round basics replenishment          |
| Brand / contract-production role | • Own-brand apparel producer • OEM garment manufacturer • Private-label supplier                  |

### SIC 24 — Lumber and Wood Products, Except Furniture

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-24)

| Industry-Specific Facets        | Example Extracted Text / Value                                              |
| ------------------------------- | --------------------------------------------------------------------------- |
| Wood species / log input        | • Southern pine • Spruce–fir • Plantation eucalyptus                        |
| Product grade / specification   | • Structural dimension lumber • Appearance-grade boards • Plywood panels    |
| Wood-processing activity        | • Logging • Sawmilling • Engineered-wood production                         |
| Log / timber-supply integration | • Purchased sawlogs • Owned timber supply • Long-term stumpage contracts    |
| Construction-demand exposure    | • Residential framing demand • Remodeling demand • Industrial pallet demand |
| Mill / log-processing capacity  | • 500 million board feet/year • 300,000 m³ of plywood/year                  |

### SIC 25 — Furniture & Fixtures

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-25)

| Industry-Specific Facets               | Example Extracted Text / Value                                                       |
| -------------------------------------- | ------------------------------------------------------------------------------------ |
| Furniture market                       | • Residential furniture • Office furniture • Hospitality fixtures                    |
| Furniture / fixture type               | • Workstations and seating • Kitchen cabinets • Retail display fixtures              |
| Production / customization model       | • Made-to-order furniture • Configurable modular systems • Standard stocked products |
| Primary materials                      | • Solid wood • Upholstered frames • Steel and engineered wood                        |
| Design / specification differentiation | • Ergonomic seating • Architect-specified fixtures • Modular space-planning system   |

### SIC 26 — Paper & Allied Products

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-26)

| Industry-Specific Facets             | Example Extracted Text / Value                                                  |
| ------------------------------------ | ------------------------------------------------------------------------------- |
| Paper / converted-product grade      | • Containerboard • Tissue • Fine paper                                          |
| Packaging / tissue / publication mix | • Corrugated packaging • Consumer tissue • Printing and writing paper           |
| Pulp / converting integration        | • Integrated pulp and paper mill • Purchased pulp • Converting-only operation   |
| Fiber furnish                        | • 70% recovered fiber • Virgin softwood pulp • Mixed hardwood pulp              |
| Mill / converting capacity           | • 1.5 million metric tonnes/year • 800,000 metric tonnes of containerboard/year |
| Energy / water requirements          | • Biomass-fired process steam • Purchased electricity • Recycled process water  |

### SIC 27 — Printing, Publishing and Allied Industries

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-27)

Commercial printers, book publishers and periodical publishers have different operating drivers. Paid circulation and advertising dependence are publisher rows, not mandatory metrics for a commercial-printing plant.

| Industry-Specific Facets                          | Example Extracted Text / Value                                                             |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Printing / publishing activity                    | • Commercial printing • Newspaper publishing • Book publishing                             |
| Print / digital revenue mix [publishers]          | • 40% print and 60% digital revenue • Digital-subscription-led publisher                   |
| Publication / print market                        | • Trade journals • Educational books • Commercial packaging print                          |
| Advertising / circulation dependence [publishers] | • 50% advertising revenue • Paid digital subscriptions • Newsstand copy sales              |
| Print output / format [printers]                  | • 100,000 magazines/month • Web-offset printing • Short-run digital printing               |
| Paid circulation [periodicals]                    | • 75,000 paid print subscriptions • 200,000 paid digital subscriptions                     |
| Rights / distribution [publishers]                | • Owned publishing rights • Third-party titles under license • Direct digital distribution |

### SIC 28 — Chemicals & Allied Products

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-28)

This major group includes pharmaceuticals and biological products as well as industrial chemicals. Use clinical-stage and drug-platform extensions only for the relevant life-science business; do not impose drug approval or patent dependence on all commodity chemicals.

| Industry-Specific Facets                    | Example Extracted Text / Value                                                                       |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Chemical / life-science product family      | • Specialty coatings • Fertilizers • Prescription pharmaceuticals                                    |
| Specialty / commodity positioning           | • Customer-qualified specialty formulations • Bulk commodity chemicals                               |
| Formulation / synthesis complexity          | • Custom additive formulation • Multistep chemical synthesis • Standardized bulk production          |
| Patent / exclusivity dependence             | • Patented active ingredient • Process know-how • Product-exclusivity expiry in 2029                 |
| Product-specific regulatory route           | • TSCA chemical compliance • REACH registration • FDA-approved medicine                              |
| R&D intensity                               | • Annual R&D: 6% of sales • Annual R&D: 18% of sales                                                 |
| Clinical / commercialization stage [pharma] | • Phase II trial program • Phase III registration study • Commercialized medicine                    |
| Biologic / small-molecule platform [pharma] | • Monoclonal antibodies • Small molecules • Vaccines                                                 |
| Manufacturing / supply model [pharma]       | • Own GMP drug manufacturing • Outsourced API manufacturing • Contract development and manufacturing |

### SIC 29 — Petroleum Refining and Related Industries

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-29)

| Industry-Specific Facets               | Example Extracted Text / Value                                                             |
| -------------------------------------- | ------------------------------------------------------------------------------------------ |
| Refining / related activity            | • Crude-oil refining • Lubricant blending • Asphalt production                             |
| Crude-processing capacity [refineries] | • 250,000 barrels/calendar day • 180,000 barrels/stream day                                |
| Product yield mix                      | • Gasoline and diesel-led output • Jet-fuel-rich output • Heavy fuel-oil output            |
| Feedstock specification                | • Medium sour crude • Light sweet crude • Heavy crude blend                                |
| Margin / crack-spread exposure         | • Gulf Coast 3-2-1 crack spread • Regional diesel cracks • Feedstock-quality differentials |
| Conversion / refinery complexity       | • Coking refinery • Hydrocracking refinery • Hydroskimming refinery                        |
| Throughput / utilization [refineries]  | • 225,000 barrels/day actual throughput • 90% of stated operable capacity                  |

### SIC 30 — Rubber & Miscellaneous Plastics

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-30)

| Industry-Specific Facets         | Example Extracted Text / Value                                                |
| -------------------------------- | ----------------------------------------------------------------------------- |
| Polymer / rubber family          | • Polypropylene • Polyethylene • Synthetic rubber                             |
| Forming / fabrication process    | • Injection molding • Extrusion • Blow molding                                |
| Component specialization         | • Custom automotive parts • Standard plastic containers • Specialty seals     |
| Mold / tooling requirements      | • Dedicated precision molds • Customer-owned tooling • Rapid-change tooling   |
| Feedstock / input-price exposure | • Resin-price pass-through • Natural-rubber prices • Petrochemical feedstocks |

### SIC 31 — Leather & Leather Products

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-31)

| Industry-Specific Facets       | Example Extracted Text / Value                                                  |
| ------------------------------ | ------------------------------------------------------------------------------- |
| Leather / material type        | • Full-grain bovine leather • Suede • Finished hides                            |
| Leather-product category       | • Footwear • Handbags • Industrial leather goods                                |
| Tanning / fabrication activity | • Tanning and finishing • Footwear manufacturing • Cut-and-sew leather goods    |
| Material / production sourcing | • Purchased finished leather • Captive tannery • Third-party contract stitching |
| Brand / manufacturing role     | • Own-brand footwear producer • Contract manufacturer for luxury brands         |

### SIC 32 — Stone, Clay, Glass & Concrete

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-32)

| Industry-Specific Facets            | Example Extracted Text / Value                                                                          |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Mineral-based product               | • Ready-mix concrete • Cement • Flat glass                                                              |
| Thermal-processing dependence       | • Cement kiln • Glass-melting furnace • Concrete batching without kiln                                  |
| Energy / fuel intensity             | • Electricity-intensive glass melting • Kiln fuel from natural gas • Diesel-intensive concrete delivery |
| Delivery radius / product logistics | • 30-mile ready-mix radius • Bulk cement by rail • Exported flat glass                                  |
| Construction end use                | • Residential foundations • Commercial glazing • Infrastructure concrete                                |
| Raw-material / integration model    | • Owned limestone quarry • Purchased cement and aggregates • Purchased glass cullet                     |

### SIC 33 — Primary Metal Industries

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-33)

| Industry-Specific Facets          | Example Extracted Text / Value                                                                               |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Metal / alloy family              | • Aluminum • Carbon steel • Copper                                                                           |
| Primary / secondary processing    | • Primary smelting • Scrap-based electric-arc furnace • Rolling and finishing                                |
| Annual production capacity        | • 300,000 metric tonnes of aluminum/year • Two million metric tonnes of steel/year                           |
| Raw-material / scrap mix          | • Alumina feedstock • 85% scrap charge • Iron ore and coke                                                   |
| Process-energy requirement        | • Electricity-intensive smelting • Gas-fired reheating • Integrated blast furnace                            |
| Metal pricing / realization basis | • LME aluminum plus regional premium • Contracted steel benchmark formula • Fixed-price metal sales contract |

### SIC 34 — Fabricated Metal Products

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-34)

| Industry-Specific Facets            | Example Extracted Text / Value                                                                                         |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Metal-fabrication process           | • CNC machining • Stamping • Forging                                                                                   |
| Precision / tolerance requirement   | • ±0.01 mm component tolerance • Micron-level machining • Structural fabrication tolerance                             |
| Custom / standardized component mix | • Custom aerospace components • Standard fasteners • Engineered pressure vessels                                       |
| Tooling / equipment capability      | • Five-axis machining • Progressive stamping dies • Large-format welding                                               |
| End-market qualifications           | • AS9100-certified aerospace quality system • Automotive IATF 16949 certification • Pressure-vessel code qualification |

### SIC 35 — Industrial and Commercial Machinery and Computer Equipment

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-35)

Computer equipment is included here in the historical U.S. SIC structure; semiconductor devices are in SIC 36. Aftermarket and installed-base metrics apply to the equipment business, not automatically to every computer-related subsidiary.

| Industry-Specific Facets                | Example Extracted Text / Value                                                                  |
| --------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Machinery / computer-equipment category | • Industrial compressors • Construction machinery • Computer servers                            |
| Installed equipment base                | • 20,000 active compressors • 50,000 installed machine tools                                    |
| Aftermarket sales mix                   | • 35% parts and service revenue • Maintenance-led recurring revenue • Equipment-only sales      |
| Equipment replacement cycle             | • 10–15-year machinery life • 3–5-year server refresh cycle                                     |
| Engineering / customization             | • Engineered-to-order machines • Configurable standard machines • Catalogue equipment           |
| Service / maintenance requirement       | • Quarterly preventive servicing • Remote condition monitoring • Customer-performed maintenance |

### SIC 36 — Electronic and Electrical Equipment, Except Computer Equipment

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-36)

| Industry-Specific Facets                         | Example Extracted Text / Value                                                                                    |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| Electrical / electronic product family           | • Power-management chips • Switchgear • Household electrical appliances                                           |
| Operating model                                  | • Fabless chip designer • Integrated semiconductor manufacturer • Electrical-equipment producer                   |
| Design / fabrication / assembly split            | • In-house IC design with outsourced wafer fabrication • Captive wafer fabrication • Outsourced assembly and test |
| Product / design-in lifecycle                    | • Annual consumer-electronics redesign • Five-year automotive design-in • Long-life industrial component          |
| OEM / design-win exposure                        | • Smartphone OEM design win • Industrial automation customers • Automotive platform nomination                    |
| Process / technology capability [semiconductors] | • 5 nm logic design • 300 mm mature-node fabrication • Advanced packaging                                         |
| Manufacturing / supply capacity [semiconductors] | • Contracted foundry wafer capacity • 40,000 wafer starts/month • Outsourced test capacity                        |

### SIC 37 — Transportation Equipment

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-37)

| Industry-Specific Facets             | Example Extracted Text / Value                                                                           |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| Transport-equipment activity         | • Commercial aircraft components • Passenger vehicles • Marine propulsion equipment                      |
| OEM / supplier role                  | • Vehicle OEM • Tier-one systems supplier • Tier-two component supplier                                  |
| Platform / program concentration     | • Two major aircraft programs • Single heavy-truck platform • Diversified vehicle platforms              |
| Product / production qualification   | • FAA production approval • Automotive IATF 16949 certification • Marine classification-society approval |
| Program backlog                      | • Four years of contracted deliveries • $2 billion of firm orders                                        |
| Aftermarket / original-equipment mix | • 30% aircraft aftermarket sales • OEM production parts • Maintenance and overhaul services              |

### SIC 38 — Measuring, Medical, Optical and Related Instruments

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-38)

Medical devices and nonmedical instruments require different regulatory and performance fields. FDA 510(k) clearance, PMA approval and other routes are distinct statuses, not interchangeable certification labels. [FDA device pathway](https://www.fda.gov/industry/fda-basics-industry/what-protocol-needs-be-followed-get-medical-device-approved).

| Industry-Specific Facets                | Example Extracted Text / Value                                                                  |
| --------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Instrument / device family              | • Diagnostic imaging systems • Industrial sensors • Laboratory analytical instruments           |
| Measurement / performance specification | • ±0.01°C temperature accuracy • 1 μm positional resolution • Stated imaging spatial resolution |
| Clinical / industrial / research use    | • Hospital diagnostics • Factory process control • Research laboratories                        |
| Product-specific regulatory status      | • FDA 510(k)-cleared device • FDA PMA-approved device • Nonmedical industrial instrument        |
| Consumables / service attachment        | • Proprietary reagent cartridges • Recurring calibration service • One-time equipment sales     |
| Calibration / qualification requirement | • Annual traceable calibration • On-site validation • Factory-only recalibration                |

### SIC 39 — Miscellaneous Manufacturing

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-39)

| Industry-Specific Facets    | Example Extracted Text / Value                                                                            |
| --------------------------- | --------------------------------------------------------------------------------------------------------- |
| Manufactured-product niche  | • Jewelry • Sporting goods • Toys                                                                         |
| Production process          | • Precision casting • Composite lay-up • Assembly of molded parts                                         |
| Customization / batch model | • Bespoke jewelry orders • Small-batch branded production • High-volume standard products                 |
| Brand / licensing economics | • Owned sporting-goods brand • Licensed toy character • Contract manufacturing                            |
| Operating production scale  | • 500,000 finished items/year • Two specialist production plants                                          |
| Product / demand cycle      | • Seasonal toy launches • Durable sporting-equipment replacements • Fashion-sensitive jewelry collections |

## E. Transportation, Communications and Utilities

### SIC 40 — Railroad Transportation

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-40)

| Industry-Specific Facets       | Example Extracted Text / Value                                                               |
| ------------------------------ | -------------------------------------------------------------------------------------------- |
| Rail service                   | • Freight railroad • Passenger rail • Short-line freight                                     |
| Network reach / route measure  | • 20,000 route-miles • Regional interchange network • Dedicated industrial rail corridor     |
| Track / infrastructure control | • Owned track • Trackage rights • Leased operating network                                   |
| Fleet / carrying capacity      | • 1,500 locomotives • 25,000 freight cars • Leased railcar fleet                             |
| Freight commodity mix          | • Intermodal containers • Grain and agricultural products • Coal and industrial materials    |
| Operating ratio                | • Operating expense / operating revenue: 65% • Adjusted operating ratio: 68%, issuer-defined |
| Service / network productivity | • Train speed: 25 mph • Terminal dwell: 20 hours • Carload traffic: 500,000/year             |

### SIC 41 — Local, Suburban and Interurban Passenger Transportation

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-41)

| Industry-Specific Facets      | Example Extracted Text / Value                                                             |
| ----------------------------- | ------------------------------------------------------------------------------------------ |
| Passenger transport mode      | • Urban bus • Commuter rail • Taxi fleet                                                   |
| Operating fleet               | • 800 buses • 120 railcars • 2,000 licensed taxis                                          |
| Route / service density       | • 150 scheduled routes • Dense metropolitan service • Interurban coach network             |
| Fare / payment structure      | • Flat single-journey fare • Distance-based fares • Monthly travel passes                  |
| Public-service contract model | • Gross-cost municipal contract • Fare-revenue-risk concession • Private commercial routes |
| Passenger utilization         | • Average vehicle load: 55% • 40 million passenger journeys/year                           |

### SIC 42 — Motor Freight Transportation and Warehousing

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-42)

| Industry-Specific Facets        | Example Extracted Text / Value                                                             |
| ------------------------------- | ------------------------------------------------------------------------------------------ |
| Freight / storage service       | • Full truckload • Less-than-truckload • Contract warehousing                              |
| Transport asset model           | • Company-owned tractors • Owner-operator network • Leased fleet                           |
| Warehouse footprint / capacity  | • Five million ft² of warehouse space • 100,000 pallet positions                           |
| Freight specialization          | • Refrigerated freight • Hazardous materials • General merchandise                         |
| Network / lane structure        | • Regional LTL terminals • Dedicated contract lanes • National long-haul network           |
| Asset-based / intermediary role | • Motor carrier • Freight broker • Integrated carrier and broker                           |
| Freight operating drivers       | • Loaded-mile percentage: 88% • Revenue per loaded mile • Warehouse space utilization: 85% |

### SIC 43 — U.S. Postal Service

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-43)

REFERENCE ONLY for the global public-company comp pool: SIC 43 is specifically the United States Postal Service. Commercial couriers are not assigned here merely because they deliver parcels; consult their actual road/air transport classification. [Official boundary](https://www.osha.gov/data/sic-manual/major-group-43).

| Industry-Specific Facets     | Example Extracted Text / Value                                                                 |
| ---------------------------- | ---------------------------------------------------------------------------------------------- |
| Postal service / product mix | • First-Class Mail • Marketing Mail • Parcel services                                          |
| Postal network               | • Post offices and delivery units • Processing and distribution centers                        |
| Delivery coverage / density  | • Nationwide address coverage • Rural delivery routes • Urban carrier routes                   |
| Delivered item volume        | • Annual letter-mail volume • Annual parcel volume                                             |
| Universal-service mandate    | • Delivery coverage obligations • Service-frequency requirements • Uniform service commitments |

### SIC 44 — Water Transportation

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-44)

| Industry-Specific Facets         | Example Extracted Text / Value                                                              |
| -------------------------------- | ------------------------------------------------------------------------------------------- |
| Vessel / marine service          | • Container shipping • Dry-bulk shipping • Tanker transport                                 |
| Fleet carrying capacity          | • 100,000 TEU container capacity • Two million deadweight tonnes • Ten product tankers      |
| Trade / shipping lanes           | • Asia–Europe routes • Trans-Pacific routes • Coastal cabotage                              |
| Charter / deployment arrangement | • Time-chartered vessels • Voyage-charter exposure • Owned vessels under long-term charters |
| Freight pricing / spot exposure  | • Spot tanker rates • Contract container freight rates • Baltic-index-linked charters       |
| Port / terminal access           | • Owned terminal interests • Long-term berth access • Third-party port calls                |
| Fleet renewal / specification    | • Average vessel age: 8 years • LNG dual-fuel vessels • Scrubber-equipped tankers           |

### SIC 45 — Air Transportation

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-45)

Passenger and cargo load factors have different traffic units. Yield per passenger-km, yield per cargo tonne-km and revenue per available seat-mile are separate measures; preserve the reported unit.

| Industry-Specific Facets   | Example Extracted Text / Value                                                    |
| -------------------------- | --------------------------------------------------------------------------------- |
| Air service                | • Scheduled passenger airline • Dedicated air cargo • Air courier                 |
| Route / network model      | • Hub-and-spoke network • Point-to-point routes • Long-haul international service |
| Fleet / aircraft mix       | • Narrow-body aircraft • Wide-body aircraft • Freighter aircraft                  |
| Load factor by service     | • Passenger RPK/ASK: 84% • Cargo tonne-km load factor: 62%                        |
| Yield / unit revenue       | • Passenger revenue/RPK • Cargo revenue/tonne-km • Passenger RASM                 |
| Fuel / fleet-cost exposure | • Jet-fuel hedging • Unhedged fuel purchases • Leased aircraft fleet              |
| Service / traffic mix      | • Premium-cabin revenue • Leisure travelers • Express parcel traffic              |

### SIC 46 — Pipelines, Except Natural Gas

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-46)

The group excludes natural-gas pipelines. Do not compare a pipeline’s rated capacity with realized throughput as though both were capacity measurements.

| Industry-Specific Facets    | Example Extracted Text / Value                                                               |
| --------------------------- | -------------------------------------------------------------------------------------------- |
| Pipeline commodity          | • Crude oil • Refined petroleum products • Slurry                                            |
| Pipeline network length     | • 2,000 pipeline-miles • 800 km trunk system                                                 |
| Throughput capacity         | • 500,000 barrels/day rated capacity • 300,000 barrels/day actual throughput                 |
| Tariff / fee structure      | • Per-barrel transportation fee • Regulated interstate tariff • Negotiated contracted tariff |
| Committed contract coverage | • Take-or-pay commitments • Minimum-volume commitments • Uncommitted spot throughput         |
| Network connectivity        | • Refinery connections • Export terminal access • Storage-hub interconnections               |

### SIC 47 — Transportation Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-47)

| Industry-Specific Facets           | Example Extracted Text / Value                                                                    |
| ---------------------------------- | ------------------------------------------------------------------------------------------------- |
| Transport-intermediary service     | • Ocean freight forwarding • Customs brokerage • Travel agency                                    |
| Transport / booking specialization | • Air freight forwarding • Multimodal logistics • Corporate travel booking                        |
| Asset ownership / control          | • Asset-light forwarding network • Controlled warehouse operations • Owned transport subsidiaries |
| Activity-volume unit               | • 200,000 TEU forwarded/year • 500,000 air-freight tonnes/year • One million travel bookings/year |
| Customs / border responsibilities  | • Customs entry preparation • Licensed customs broker • Cross-border documentation                |
| Gross / net revenue presentation   | • Freight purchases passed through gross • Net commission revenue • Agency booking fees           |

### SIC 48 — Communications

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-48)

Choose telecom, broadband or broadcast rows by operating activity. Subscription ARPU/churn are not universal broadcast-company measures. Network coverage, population coverage and homes passed use different denominators.

| Industry-Specific Facets                        | Example Extracted Text / Value                                                                     |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Communications activity                         | • Mobile telecom • Fixed broadband • Radio / television broadcasting                               |
| Network / distribution assets                   | • Owned mobile network • Fiber access network • Leased broadcast distribution                      |
| Subscriber / audience measure                   | • Five million mobile connections • One million broadband accounts • Television households reached |
| License / spectrum rights                       | • Mid-band mobile spectrum • Broadcast station licenses • Cable franchise rights                   |
| ARPU / ARPA [subscription telecom]              | • $55/month per mobile user • $70/month per broadband account                                      |
| Customer churn [subscription telecom]           | • 1.2% monthly mobile-account churn • 0.8% monthly broadband-account churn                         |
| Coverage / distribution reach                   | • 95% population coverage • Two million fiber homes passed • 40 broadcast markets                  |
| Advertising / carriage economics [broadcasting] | • Local advertising revenue • Retransmission-consent fees • Network-affiliate payments             |

### SIC 49 — Electric, Gas & Sanitary Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-49)

Select the electric, gas, water, sanitary/waste, steam or irrigation branch. Generation mix and rate base are not universal requirements. MW capacity, GW peak demand, MWh generation, and generation capacity factor are different quantities. Waste disposal also needs permitted capacity and remaining airspace. [Official scope](https://www.osha.gov/data/sic-manual/major-group-49); [EIA capacity explanation](https://www.eia.gov/tools/FAQs/faq.php?id=104&t=3).

| Industry-Specific Facets                               | Example Extracted Text / Value                                                                                                            |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Utility / environmental service                        | • Electricity distribution • Water supply • Solid-waste collection                                                                        |
| Regulated / competitive operating model                | • Rate-regulated utility • Merchant generation • Contracted waste services                                                                |
| Generation fuel / technology mix [electric generators] | • 60% of net generation from gas • Wind and solar generation • Nuclear generation                                                         |
| Approved regulatory rate base [regulated utilities]    | • $4 billion rate base at year-end • £2 billion regulated asset value                                                                     |
| Connections / service accounts                         | • 900,000 electricity accounts • 200,000 water connections • 50,000 waste-service customers                                               |
| Service-specific rated capacity                        | • 2,500 MW nameplate generation • 50 million U.S. gallons/day water treatment • 1.2 million metric tonnes/year permitted waste throughput |
| Regulatory jurisdiction                                | • State public utility commission • Municipal water authority • Environmental permit authority                                            |
| Electricity output [generators]                        | • Net generation: 10 TWh/year • Net generation: 20 TWh/year                                                                               |
| Generator capacity factor [generators]                 | • 45% annual net capacity factor • 85% annual net capacity factor                                                                         |
| System peak demand [electric networks]                 | • Annual peak demand: 3 GW • Summer peak demand: 5 GW                                                                                     |
| Gas network / delivery [gas utilities]                 | • 8,000 distribution-pipeline miles • 50 million MMBtu annual deliveries                                                                  |
| Water / wastewater operations                          | • Drinking-water treatment • Wastewater treatment • Sewer-network operations                                                              |
| Water-system performance                               | • Non-revenue water: 15% of system input • Effluent-permit compliance • Water-main replacement program                                    |
| Waste / disposal economics [sanitary services]         | • Collection routes • Owned landfills • Transfer stations                                                                                 |
| Remaining landfill airspace [landfills]                | • 20 million m³ of permitted remaining airspace • 30 million cubic yards of permitted remaining airspace                                  |
| Waste accepted [disposal]                              | • Five million metric tonnes/year • Two million short tons/year                                                                           |
| Steam / irrigation service                             | • District steam distribution • Chilled-water supply • Irrigation canal delivery                                                          |

## F. Wholesale Trade

### SIC 50 — Wholesale Trade — Durable Goods

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-50)

| Industry-Specific Facets             | Example Extracted Text / Value                                                             |
| ------------------------------------ | ------------------------------------------------------------------------------------------ |
| Durable-goods distribution specialty | • Industrial bearings • Electronic components • Building materials                         |
| Distribution authorization           | • Authorized OEM distributor • Independent distributor • Exclusive territorial distributor |
| Inventory turnover                   | • Annual COGS / average inventory: 5× • Annual inventory turnover: 7×                      |
| Manufacturer / supplier relationship | • Multiyear OEM distribution agreement • Supplier rebates • Vendor-managed inventory       |
| Technical / value-added services     | • Application engineering • Component kitting • Equipment configuration                    |
| Aftermarket sales exposure           | • 60% replacement-parts sales • New-equipment supply • Maintenance-product replenishment   |

### SIC 51 — Wholesale Trade — Nondurable Goods

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-51)

| Industry-Specific Facets                | Example Extracted Text / Value                                                                          |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Nondurable-goods distribution specialty | • Fresh produce • Pharmaceuticals • Petroleum products                                                  |
| Shelf-life / handling exposure          | • Fresh produce with days of saleable life • Controlled drug storage • Ambient packaged goods           |
| Cold-chain requirement                  | • Refrigerated warehouses • Frozen-food trucks • No temperature-control requirement                     |
| Commodity / purchase-price exposure     | • Spot produce prices • Petroleum-price pass-through • Contracted branded-product costs                 |
| Delivery frequency                      | • Daily grocery-store deliveries • Weekly foodservice replenishment • Scheduled bulk-fuel deliveries    |
| Saleable shelf life                     | • 3–7 days for fresh produce • 12 months for packaged foods • Product-expiry-controlled pharmaceuticals |

## G. Retail Trade

### SIC 52 — Building Materials, Hardware, Garden Supply and Mobile Home Dealers

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-52)

| Industry-Specific Facets         | Example Extracted Text / Value                                                     |
| -------------------------------- | ---------------------------------------------------------------------------------- |
| Professional / DIY customer mix  | • 60% sales to contractors • DIY-led customer base                                 |
| Building / garden assortment     | • Lumber and hardware • Garden supplies • Manufactured-home retail                 |
| Retail format                    | • Warehouse-format home center • Builders' merchant branch • Garden center         |
| Construction / renovation demand | • New-homebuilding demand • Repair-and-remodel demand • Seasonal gardening demand  |
| Installation / project services  | • Installer referral program • Managed installation service • Materials-only sales |

### SIC 53 — General Merchandise Stores

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-53)

| Industry-Specific Facets          | Example Extracted Text / Value                                                             |
| --------------------------------- | ------------------------------------------------------------------------------------------ |
| General-merchandise retail format | • Discount department store • Department store • Variety store                             |
| Merchandise category mix          | • Apparel, home and essentials • Broad discount assortment • General merchandise with food |
| Private-label sales share         | • 25% of merchandise sales • 10% of merchandise sales                                      |
| Store sales productivity          | • $350/ft² of selling area/year • $500/ft² of selling area/year                            |
| Inventory turnover                | • Annual COGS / average inventory: 6× • Annual inventory turnover: 8×                      |
| Comparable-store sales            | • Annual comparable-store sales: +3% • Quarterly comparable-store sales: −1%               |

### SIC 54 — Food Stores

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-54)

| Industry-Specific Facets             | Example Extracted Text / Value                                                                          |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| Food retail format                   | • Full-service supermarket • Discount grocery • Convenience food store                                  |
| Fresh / packaged food mix            | • 35% fresh food sales • Packaged-food-led assortment                                                   |
| Private-label sales share            | • 20% of sales • 35% of sales                                                                           |
| Fresh-food waste / perishability     | • Daily fresh-food replenishment • 2% of fresh sales lost to spoilage • Long-life dry grocery inventory |
| Store network density                | • 50 stores in one metropolitan area • Regional supermarket clusters                                    |
| Average transaction basket           | • $48 net sales/transaction • $72 net sales/transaction                                                 |
| Customer traffic / comparable growth | • Transactions +2% year over year • Comparable sales +4% year over year                                 |

### SIC 55 — Automotive Dealers and Gasoline Service Stations

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-55)

Separate vehicle dealers from gasoline/convenience-store operations. F&I and dealership authorization are dealer rows; fuel throughput and per-gallon margin are station rows. Ancillary dealer/service-station repairs do not automatically make the establishment SIC 75.

| Industry-Specific Facets                      | Example Extracted Text / Value                                                                                 |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Dealer / fuel-retail activity                 | • Franchised vehicle dealer • Used-car retailer • Gasoline service station                                     |
| Vehicle sales mix [dealers]                   | • 55% new and 45% used unit sales • Used-vehicle-only sales                                                    |
| Vehicle brand / franchise mix [dealers]       | • Three manufacturer franchises • Single-brand dealership group                                                |
| F&I economics [dealers]                       | • $1,800 F&I gross profit/retail vehicle • 45% financing-product penetration                                   |
| Parts / service economics [dealers]           | • 30% of dealership gross profit from service • Customer-pay repair orders • Warranty repair revenue           |
| Dealership authorization [dealers]            | • Manufacturer-authorized franchise • Independent used-car dealership                                          |
| Fuel / convenience-store economics [stations] | • 10 million U.S. gallons sold/year • Fuel gross margin: $0.25/gallon • Merchandise sales: 30% of retail sales |

### SIC 56 — Apparel & Accessory Stores

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-56)

| Industry-Specific Facets           | Example Extracted Text / Value                                                     |
| ---------------------------------- | ---------------------------------------------------------------------------------- |
| Apparel-store niche                | • Women's casual apparel • Footwear • Workwear retail                              |
| Fashion / assortment cadence       | • Four seasonal collections • Weekly fashion drops • Replenishment basics          |
| Brand assortment                   | • Owned-label merchandise • Third-party brands • Multi-brand concessions           |
| Full-price / off-price mix         | • 70% full-price sales • Off-price buying model • Outlet-led sales                 |
| Markdown / inventory exposure      | • Seasonal clearance inventory • Short fashion lead times • Carryover basic styles |
| Store / online channel integration | • Click-and-collect • Ship-from-store • Store-only retail                          |

### SIC 57 — Home Furniture & Equipment Stores

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-57)

| Industry-Specific Facets              | Example Extracted Text / Value                                                                   |
| ------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Home-goods retail category            | • Furniture and mattresses • Household appliances • Consumer electronics                         |
| Delivery / installation proposition   | • White-glove furniture delivery • Appliance installation • Customer collection                  |
| Customer-financing penetration        | • 40% of transactions financed • Third-party installment financing                               |
| Transaction size / replacement demand | • $2,000 average furniture order • Appliance replacement demand • Home-move-driven purchases     |
| Inventory / fulfillment model         | • Stocked local distribution centers • Supplier drop-shipping • Made-to-order furniture delivery |

### SIC 58 — Eating & Drinking Places

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-58)

Keep system, franchised and company-operated unit counts separate. AUV, same-store sales, traffic, average check and restaurant contribution margin have different populations and definitions. Franchisee system sales are not the franchisor’s recognized revenue. [Official scope](https://www.osha.gov/data/sic-manual/major-group-58).

| Industry-Specific Facets                 | Example Extracted Text / Value                                                                        |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Restaurant / drinking-place format       | • Quick-service • Full-service casual dining • Alcohol-focused bar                                    |
| Franchise / company-operated footprint   | • 90% of system restaurants franchised • Company-operated chain • Mixed franchised and operated units |
| Comparable-unit sales growth             | • Annual same-store sales: +3% • Quarterly comparable sales: −1%                                      |
| Comparable traffic / average check       | • Transactions: −2% • Average check: +5%                                                              |
| Average unit volume [defined cohort]     | • $1.8 million annual sales/eligible restaurant • $2.5 million annual franchised-unit sales           |
| System / operated unit counts            | • 2,400 system restaurants • 180 company-operated units • 600 franchised units                        |
| Menu / beverage focus                    | • Burgers and sandwiches • Pizza • Coffee and bakery                                                  |
| Ordering / delivery sales mix            | • 20% of sales through delivery • Drive-through-led sales • Third-party delivery partnerships         |
| Store-level economics [company-operated] | • Restaurant contribution margin: 18%, issuer-defined • Food and labor cost: 60% of restaurant sales  |

### SIC 59 — Miscellaneous Retail

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-59)

| Industry-Specific Facets             | Example Extracted Text / Value                                                                     |
| ------------------------------------ | -------------------------------------------------------------------------------------------------- |
| Specialty retail niche               | • Pharmacy • Pet supplies • Jewelry                                                                |
| Merchandise specialization           | • Prescription and OTC medicines • Pet food and accessories • Fine jewelry                         |
| Retail / selling format              | • Neighborhood pharmacy • Specialty superstore • Catalogue / online retailer                       |
| Purchase / refill cadence            | • Monthly prescription refills • Weekly pet-food replenishment • Occasion-driven jewelry purchases |
| Online sales penetration             | • 12% of net sales online • 45% of net sales online                                                |
| Product-specific regulatory exposure | • Pharmacy dispensing licenses • Age-restricted product sales • Product-traceability requirements  |

## H. Finance, Insurance and Real Estate

### SIC 60 — Depository Institutions

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-60)

NIM uses net interest income over average earning assets, not total revenue. Total-deposit cost and interest-bearing-deposit cost are separate measures. NPL, nonaccrual and delinquency definitions must not be silently equated. [Federal Reserve NIM definition](https://www.federalreserve.gov/econresdata/notes/ifdp-notes/2016/low-for-long-interest-rates-and-net-interest-margins-of-banks-in-advanced-foreign-economies-20160411.html).

| Industry-Specific Facets          | Example Extracted Text / Value                                                                                       |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Deposit composition               | • Retail transaction deposits • Commercial deposits • Time deposits                                                  |
| Lending composition               | • Residential mortgages • Commercial and industrial loans • Credit cards                                             |
| Net interest margin               | • Annualized NII / average earning assets: 3.1% • Tax-equivalent NIM: 3.4%, separately identified                    |
| Deposit interest cost             | • 1.2% annualized cost on average total deposits • 2.0% annualized cost on average interest-bearing deposits         |
| Nonperforming-loan measure        | • NPLs / gross loans: 0.8% • Nonaccrual loans / loans: 1.1%                                                          |
| Regulatory capital measure        | • CET1 / risk-weighted assets: 12% • Total capital / risk-weighted assets: 15%                                       |
| Liquidity / deposit concentration | • Uninsured deposits: 35% of total deposits • High-quality liquid-asset portfolio • Concentrated commercial deposits |

### SIC 61 — Nondepository Credit Institutions

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-61)

| Industry-Specific Facets           | Example Extracted Text / Value                                                                                   |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Credit / lending product           | • Unsecured consumer loans • Auto loans • Commercial receivables finance                                         |
| Origination channel                | • Direct online origination • Dealer-originated lending • Broker-originated loans                                |
| Funding / balance-sheet model      | • Deposits unavailable; warehouse-funded lender • Debt-funded retained loan book • Originate-to-distribute model |
| Loan portfolio yield               | • Annualized interest income / average loans: 14% • Reported effective yield: 9%                                 |
| Delinquency by aging bucket        | • 30+ days past due: 4% of loans • 90+ days past due: 1.5% of loans                                              |
| Securitization / retained exposure | • Regular ABS issuance • Retained first-loss interests • Servicing rights retained after sale                    |
| Credit-loss measure                | • Annualized net charge-offs: 3% of average loans • Vintage cumulative loss: 6%                                  |

### SIC 62 — Security and Commodity Brokers, Dealers, Exchanges and Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-62)

Separate asset managers, brokers, dealers and exchanges. AUM, AUA and assets under custody describe different roles and may overlap; do not add them together or treat them as interchangeable company scale.

| Industry-Specific Facets                          | Example Extracted Text / Value                                                  |
| ------------------------------------------------- | ------------------------------------------------------------------------------- |
| Financial-market service                          | • Retail brokerage • Investment advisory • Securities market making             |
| Client / instrument exposure                      | • Retail equities and ETFs • Institutional fixed income • Listed derivatives    |
| Assets under management [asset managers]          | • $80 billion discretionary AUM • $20 billion non-discretionary AUM             |
| Assets under administration / custody [platforms] | • $100 billion client AUA • $300 billion assets under custody                   |
| Revenue / fee economics                           | • Asset-based advisory fees • Brokerage commissions • Principal trading revenue |
| Client trading activity                           | • One million executed trades/day • Ten million options contracts/month         |

### SIC 63 — Insurance Carriers

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-63)

Combined ratio is an underwriting measure for P&C operations, not a universal life-insurance profitability metric. Preserve gross/net, calendar/accident-year, catastrophe exclusions and the issuer’s expense-ratio basis. Life/annuity and health businesses need liability/benefit measures instead. [NAIC terminology](https://content.naic.org/glossary-insurance-terms?id=37).

| Industry-Specific Facets                           | Example Extracted Text / Value                                                                                       |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Insurance business line                            | • Commercial P&C • Life and annuity insurance • Health insurance                                                     |
| Risk underwriting / distribution model             | • Direct primary insurer • Reinsurer • Delegated underwriting with retained risk                                     |
| Premium / exposure mix                             | • 60% commercial auto and 40% property premiums • Individual annuity-led sales                                       |
| Combined ratio [P&C underwriting]                  | • Calendar-year combined ratio: 96% • Accident-year ratio excluding catastrophes: 91%, separately defined            |
| Loss / LAE ratio [P&C underwriting]                | • Net loss and LAE / net earned premiums: 64% • Accident-year loss and LAE ratio: 60%                                |
| Medical benefit ratio [health insurers]            | • Medical benefits / premium revenue: 82% • Issuer-defined medical loss ratio: 85%                                   |
| Reinsurance / catastrophe protection               | • Quota-share cessions • Excess-of-loss catastrophe cover • Retained catastrophe limit                               |
| Liability duration / guarantees [life and annuity] | • Fixed deferred annuities • Variable annuities with guarantees • Long-duration protection liabilities               |
| Investment / liability matching                    | • Duration-matched bond portfolio • Interest-rate hedges for annuity guarantees • Separate-account investment assets |
| Regime-specific solvency measure                   | • U.S. insurance RBC ratio, denominator identified • EU Solvency II coverage ratio                                   |

### SIC 64 — Insurance Agents, Brokers & Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-64)

Distinguish policy-count renewal, client-count retention and premium/revenue retention. Commissions and contingent commissions are intermediary compensation, not underwriting profit.

| Industry-Specific Facets    | Example Extracted Text / Value                                                                    |
| --------------------------- | ------------------------------------------------------------------------------------------------- |
| Insurance intermediary role | • Independent broker • Exclusive agent • Third-party administrator                                |
| Insurance placement niche   | • Commercial P&C • Employee benefits • Personal lines                                             |
| Intermediary compensation   | • Carrier-paid commissions • Client advisory fees • Contingent commissions                        |
| Policy / account renewal    | • 92% of expiring policies renewed • 90% of expiring client accounts renewed                      |
| Carrier / market access     | • Multiple carrier appointments • Wholesale placement relationships • Single-carrier distribution |
| Client retention by measure | • Annual client-count retention: 92% • Renewal-premium retention: 95%                             |

### SIC 65 — Real Estate

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-65)

Owner, broker and third-party property-manager models require different fields. Physical occupancy, economic occupancy, rent per unit and rent per area are distinct measures. A company being a REIT does not itself assign it to SIC 65: official SIC 6798 is under major group 67. [REIT classification](https://www.osha.gov/sic-manual/6798).

| Industry-Specific Facets            | Example Extracted Text / Value                                                                               |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Property / real-estate service type | • Multifamily apartments • Industrial warehouses • Property brokerage                                        |
| Ownership / operating role          | • Direct property owner • Property manager for third parties • Real-estate broker                            |
| Occupancy by basis [owners]         | • Physical leased-unit occupancy: 95% • Leased-area occupancy: 92% • Economic occupancy: 94%, issuer-defined |
| Lease term [owners]                 | • Typical residential lease: 12 months • Rent-weighted unexpired lease term: 6.5 years                       |
| Rent by property unit [owners]      | • $2,200/unit/month • $25/ft²/year base rent                                                                 |
| Property market                     | • Sun Belt metropolitan areas • Central London offices • Regional industrial corridors                       |
| Property-income / fee model         | • Rental income and recoveries • Percentage-of-rent management fee • Brokerage commission per transaction    |

### SIC 67 — Holding & Other Investment Offices

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-67)

Distinguish operating holding companies, investment vehicles, equity REITs and mortgage REITs. Use look-through operating-segment modules for controlled businesses; do not treat fund AUM, NAV and consolidated operating revenue as equivalent scale. Property extensions can be shared with SIC 65 without changing the source’s official code. [REIT scope](https://www.osha.gov/sic-manual/6798).

| Industry-Specific Facets                                  | Example Extracted Text / Value                                                                     |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Holding / investment-office structure                     | • Operating holding company • Closed-end investment vehicle • Equity REIT                          |
| Investment / operating asset mix                          | • Controlled industrial subsidiaries • Listed securities portfolio • Income-producing property     |
| Control / look-through ownership                          | • Majority-owned subsidiaries • Minority equity stakes • Noncontrolling fund investments           |
| Portfolio concentration                                   | • Three holdings: 70% of NAV • Single-sector investment portfolio                                  |
| Management / incentive fees [externally managed vehicles] | • No external manager fee • 1% of NAV annual management fee • Performance fee above stated hurdle  |
| NAV basis [investment vehicles]                           | • Reported NAV/share at quarter-end • Reported portfolio NAV at year-end                           |
| Parent funding / subsidiary recourse                      | • Parent-only net debt • Ring-fenced subsidiary borrowings • Parent-guaranteed subsidiary debt     |
| Market discount [listed investment vehicles]              | • Share price 15% below disclosed NAV/share • Share price 5% above disclosed NAV/share             |
| REIT business model [6798]                                | • Equity REIT owning properties • Mortgage REIT holding loan assets                                |
| Property portfolio [equity REITs]                         | • Multifamily apartments • Industrial warehouses • Data-center properties                          |
| Property occupancy [equity REITs]                         | • 95% physically occupied units • 92% leased floor area                                            |
| Same-property NOI growth [equity REITs]                   | • Annual same-property NOI: +3% • Quarterly same-property NOI: −1%                                 |
| Lease expiry [equity REITs]                               | • 20% of annual base rent expires within two years • Rent-weighted unexpired lease term: 6.5 years |
| Mortgage asset mix [mortgage REITs]                       | • Agency residential MBS • Commercial mortgage loans • Nonagency mortgage securities               |
| Financing / hedge model [mortgage REITs]                  | • Repo-funded MBS portfolio • Match-funded commercial mortgages • Interest-rate swap hedges        |

## I. Services

### SIC 70 — Hotels and Other Lodging Places

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-70)

ADR is room revenue per room sold; RevPAR is room revenue per available room over the same period. Neither is total hotel revenue per room. Separate owned, managed, franchised and system room populations. [STR/CoStar glossary](https://costar-na-prod.acquia.dshrp.com/products/str-benchmark/resources/glossary).

| Industry-Specific Facets                               | Example Extracted Text / Value                                                                                           |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| Lodging / operating format                             | • Full-service hotel • Limited-service hotel • Holiday camp                                                              |
| Room inventory / ownership scope                       | • 3,500 owned rooms • 20,000 managed rooms • 80,000 system rooms                                                         |
| ADR [room operators]                                   | • $175 room revenue/sold room-night • $220 room revenue/sold room-night                                                  |
| RevPAR [room operators]                                | • $130 room revenue/available room-night • $160 room revenue/available room-night                                        |
| Room occupancy [room operators]                        | • Sold room-nights / available room-nights: 74% • Same-property occupancy: 80%                                           |
| Ownership / management / franchising                   | • Owned hotels • Third-party managed hotels • Franchised hotel brands                                                    |
| Hotel demand / seasonality                             | • Summer resort peak • Weekday corporate demand • Conference-led group demand                                            |
| Brand fee / contract economics [asset-light operators] | • Franchise royalty on hotel room revenue • Base management fee on hotel revenue • Incentive fee on defined hotel profit |

### SIC 72 — Personal Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-72)

| Industry-Specific Facets                       | Example Extracted Text / Value                                                                 |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Personal-service specialty                     | • Hair salons • Dry cleaning • Funeral services                                                |
| Purchase / service cadence                     | • Hair appointments every 6–8 weeks • Weekly laundry collection • One-time funeral arrangement |
| Outlet / catchment concentration               | • 30 salons in two cities • Regional dry-cleaning outlets • Local funeral-home network         |
| Service-specific labor qualification           | • Licensed cosmetologists • Trained textile-care technicians • Licensed funeral directors      |
| Repeat-customer measure                        | • Annual returning-client share: 65% • Annual active-client retention: 80%                     |
| Appointment rebooking [appointment businesses] | • 50% of appointments rebooked • 70% of clients prebook their next visit                       |

### SIC 73 — Business Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-73)

This is not a SaaS-only template. Choose the relevant 731 advertising, 734 building-services, 735 rental, 736 staffing, 737 computer-services/software or 738 specialist-services branch. SIC4 examples are routing aids, not new official business-model categories. NRR, ARR and software implementation fields are conditional software rows. [Official scope and detailed groups](https://www.osha.gov/data/sic-manual/major-group-73).

| Industry-Specific Facets                                | Example Extracted Text / Value                                                                             |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Business-service specialization                         | • Packaged HCM software • Temporary staffing • Building cleaning                                           |
| Service operating model                                 | • Subscription software • Labor-based outsourcing • Project-based agency                                   |
| Charging unit                                           | • Per employee/month • Per billable labor hour • Per processed transaction                                 |
| Customer contract term                                  | • Month-to-month service • Annual subscription • Three-year managed-service agreement                      |
| Contracted / repeat revenue                             | • 80% subscription revenue • Recurring cleaning contracts • Repeat usage-based processing fees             |
| Implementation / transition work                        | • Payroll data migration • Outsourcing transition • Customer-site service mobilization                     |
| Client-count retention                                  | • Annual paying-client retention: 92% • Annual retained service accounts: 90%                              |
| Software deployment [737 software/services]             | • Multi-tenant SaaS • Customer-hosted software • Hybrid deployment                                         |
| Software functional scope [737]                         | • Payroll and HCM • Cybersecurity • ERP / accounting                                                       |
| Net revenue retention [subscription software]           | • Annual NRR: 115% • Annual constant-currency NRR: 108%, separately defined                                |
| ARR / recurring-base definition [subscription software] | • Subscription ARR at year-end • Annualized contracted recurring fees, issuer-defined                      |
| Processing / transaction platform [7374]                | • Payroll processing • Card-transaction processing • Data preparation services                             |
| Staffing / placement model [736]                        | • Temporary staffing • Permanent placement • Recruitment process outsourcing                               |
| Temporary staffing activity [temporary staffing]        | • 10,000 workers on assignment • Two million billed temporary-worker hours/year                            |
| Permanent placement volume [employment agencies]        | • 3,000 placements/year • 1,500 placements/year                                                            |
| Temporary labor billing economics [temporary staffing]  | • Bill rate $40/hour versus pay rate $28/hour • Stated markup on direct labor cost                         |
| Advertising / agency economics [731]                    | • Media-placement commission • Creative-service retainer • Performance-marketing fee                       |
| Building / security service model [734, 7381–7382]      | • Contract janitorial routes • On-site guarding • Monitored security installations                         |
| Rental fleet / utilization [735]                        | • Construction-equipment rental • Medical-equipment rental • Time utilization: 70% of eligible rental days |

### SIC 75 — Automotive Repair, Services & Parking

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-75)

Rental fleets, repair bays and parking spaces are different capacity measures. Finance leasing and repairs incidental to a car dealership have separate SIC boundaries; do not label all vehicle-related services SIC 75. [Official scope](https://www.osha.gov/data/sic-manual/major-group-75).

| Industry-Specific Facets                    | Example Extracted Text / Value                                                                                      |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Automotive-service activity                 | • Vehicle repair • Vehicle rental • Parking operations                                                              |
| Rental fleet [rental businesses]            | • 20,000 available vehicles • Leased commercial-vehicle fleet                                                       |
| Workshop / bay capacity [repair businesses] | • 120 service bays • 30 repair locations                                                                            |
| Operating utilization by activity           | • 78% of eligible rental vehicle-days • 85% occupied parking space-hours • 70% technician billable-time utilization |
| Service / maintenance cycle                 | • Mileage-based fleet servicing • Scheduled customer maintenance • Emergency breakdown repairs                      |
| Parking / rental revenue unit               | • Revenue per available rental day • Hourly parking fee • Monthly parking contract                                  |

### SIC 76 — Miscellaneous Repair Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-76)

| Industry-Specific Facets         | Example Extracted Text / Value                                                                |
| -------------------------------- | --------------------------------------------------------------------------------------------- |
| Repair equipment / product niche | • Industrial pumps • Consumer appliances • Electrical motors                                  |
| Repair technical scope           | • Mechanical overhaul • Electronic diagnostics • Component-level replacement                  |
| Warranty / customer-pay mix      | • Manufacturer warranty repairs • Customer-paid repairs • Third-party warranty administration |
| Replacement-parts requirement    | • OEM seals and bearings • Refurbished components • Proprietary diagnostic parts              |
| Service-contract coverage        | • 40% of customer equipment under maintenance agreements • Break-fix jobs only                |

### SIC 78 — Motion Pictures

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-78)

A production company, content distributor and cinema exhibitor are not direct peers solely because they share SIC 78. Content rights and production budgets do not substitute for cinema screens or admissions.

| Industry-Specific Facets                                  | Example Extracted Text / Value                                                                 |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Film / video value-chain role                             | • Film production • Content distribution • Cinema exhibition                                   |
| Content-library rights                                    | • 200 owned film titles • Licensed distribution catalogue • No owned content library           |
| Licensed-rights scope                                     | • Territorial rights • Five-year streaming window • Exclusive theatrical rights                |
| Revenue / release window                                  | • Theatrical box office • Streaming-license fees • Cinema ticket and concession sales          |
| Project / acquisition commitment [producers/distributors] | • $30 million production budget • $10 million minimum guarantee • Co-financed production slate |
| Exhibition footprint [cinemas]                            | • 500 cinema screens • 100,000 cinema seats                                                    |

### SIC 79 — Amusement & Recreation

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-79)

Theme parks, fitness clubs, sports and gaming have different unit economics. Gaming win percentages are not ticket yields, and membership counts are not visits.

| Industry-Specific Facets             | Example Extracted Text / Value                                                              |
| ------------------------------------ | ------------------------------------------------------------------------------------------- |
| Recreation / entertainment activity  | • Theme park • Fitness clubs • Professional sports promotion                                |
| Venue / service capacity             | • 20,000 permitted guests/day • 5,000 arena seats • 2,000 fitness members/location          |
| Visits / event attendance            | • Three million annual park visits • 80 home events/year • One million paid admissions/year |
| Admission yield                      | • Ticket revenue / paid admissions: $65 • Event ticket revenue / attendance: $90            |
| Pass / membership mix                | • 25% of visits from passholders • 60% of revenue from memberships                          |
| Seasonality / utilization            | • Summer-led park attendance • Evening fitness peak • Event-day-only arena operation        |
| Gaming economics [gaming businesses] | • Gross gaming revenue • Slot-machine count • House win as share of wagered amounts         |

### SIC 80 — Health Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-80)

Use setting-specific units: visits, discharges, staffed beds and dialysis stations are not interchangeable. Distinguish an organization delivering medical care from one only underwriting medical insurance. [Provider/insurer boundary](https://www.osha.gov/data/sic-manual/major-group-80).

| Industry-Specific Facets      | Example Extracted Text / Value                                                                        |
| ----------------------------- | ----------------------------------------------------------------------------------------------------- |
| Healthcare-provider setting   | • Hospital • Outpatient clinic • Home-health provider                                                 |
| Clinical specialty            | • Orthopedics • Oncology • Primary care                                                               |
| Patient activity / volume     | • 200,000 outpatient visits/year • 15,000 inpatient discharges/year • 500,000 home-health visits/year |
| Payer revenue mix             | • 40% commercial insurance • 35% Medicare • 20% Medicaid                                              |
| Payment / reimbursement model | • Fee-for-service • Case-based bundled payment • Per-member capitation                                |
| Setting-specific capacity     | • 250 staffed hospital beds • 25 clinics • 100 outpatient treatment stations                          |
| Patient acuity / case mix     | • Routine outpatient visits • High-acuity inpatient care • Reported case-mix index                    |
| Clinical operating quality    | • 30-day readmission rate • Hospital-acquired infection rate • Documented patient-safety measure      |

### SIC 81 — Legal Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-81)

| Industry-Specific Facets    | Example Extracted Text / Value                                                             |
| --------------------------- | ------------------------------------------------------------------------------------------ |
| Legal practice specialty    | • Corporate M&A • Patent litigation • Employment law                                       |
| Matter / case mix           | • Transactional advisory • Commercial litigation • Regulatory representation               |
| Billing / realization model | • Hourly billing • Fixed fee per matter • Contingent success fee                           |
| Professional leverage       | • Three associates/partner • Two billable professionals/partner                            |
| Client / engagement type    | • Mid-market corporations • Financial institutions • Individual clients                    |
| Engagement duration         | • Three-month transaction mandate • Two-year litigation matter • Ongoing advisory retainer |

### SIC 82 — Educational Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-82)

Enrollment, FTE students and course registrations are separate measures. Graduation/completion/employment rates need the entering cohort, observation window and program type.

| Industry-Specific Facets           | Example Extracted Text / Value                                                                                      |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Education level / institution type | • Postsecondary institution • K–12 school • Vocational training provider                                            |
| Program / qualification            | • Bachelor's degree • Nursing diploma • Professional certificate                                                    |
| Enrollment by measure              | • 8,000 enrolled students • 6,000 full-time-equivalent students • 2,000 annual course registrations                 |
| Tuition / payment model            | • Annual tuition • Per-course fees • Employer-funded training                                                       |
| Accreditation / authorization      | • Named institutional accreditor • Program-specific accreditation • Government operating license                    |
| Completion / student outcomes      | • Six-year degree completion: 70% • 12-month certificate completion: 85% • Graduate employment rate, defined cohort |
| Delivery / campus model            | • Campus-based instruction • Online-only programs • Hybrid courses                                                  |

### SIC 83 — Social Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-83)

Separate delivery of social/day-care services from government program administration in SIC 94. Private contractors performing the service do not become public-administration entities merely because a government pays them.

| Industry-Specific Facets         | Example Extracted Text / Value                                                                      |
| -------------------------------- | --------------------------------------------------------------------------------------------------- |
| Social-service program           | • Child day care • Vocational rehabilitation • Family support services                              |
| Beneficiary / service population | • Preschool children • Adults with disabilities • Housing-insecure families                         |
| Public / grant funding exposure  | • Local government service contract • Restricted program grants • Participant fees                  |
| Payment / reimbursement unit     | • Fee per child-day • Payment per funded service place • Grant-funded program budget                |
| Program capacity / caseload      | • 1,500 distinct clients/year • 600 licensed child-care places • 200 active case-management clients |

### SIC 84 — Museums, Art Galleries, Botanical and Zoological Gardens

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-84)

Zoological gardens are included in the official major-group scope. Admission income, grants, gifts and endowment distributions are different funding sources; nonprofit institutions are not assumed to be listed operating-company candidates.

| Industry-Specific Facets       | Example Extracted Text / Value                                                                             |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| Institution / attraction type  | • Art museum • Botanical garden • Zoo                                                                      |
| Collection / exhibit focus     | • Contemporary art • Native plant collections • Wildlife conservation exhibits                             |
| Operating funding mix          | • Admission receipts • Donations and grants • Public operating subsidy                                     |
| Visitor attendance             | • 400,000 annual visits • 250,000 paid admissions/year                                                     |
| Membership economics           | • 10,000 household memberships • $150 annual family membership                                             |
| Endowment / restricted funding | • Annual endowment distribution supports operations • Restricted conservation grants • No endowment income |

### SIC 86 — Membership Organizations

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-86)

Membership organizations can be nonprofit, religious, labor or trade bodies. Verify entity type and listing eligibility before admitting a company to a public-comp pool; do not treat all memberships as commercial subscriptions.

| Industry-Specific Facets          | Example Extracted Text / Value                                                           |
| --------------------------------- | ---------------------------------------------------------------------------------------- |
| Membership-organization type      | • Trade association • Labor union • Religious organization                               |
| Member base / counting unit       | • 20,000 individual members • 2,000 member firms • 500 affiliated congregations          |
| Dues / contribution model         | • Annual individual dues • Employer-size-tiered corporate dues • Voluntary contributions |
| Member retention                  | • Annual eligible-member renewals: 88% • Annual member-organization renewals: 93%        |
| Event / sponsorship income        | • Conference sponsorships • Exhibition-space fees • Member-event registrations           |
| Representation / mission activity | • Industry policy advocacy • Collective bargaining • Religious services                  |

### SIC 87 — Engineering, Accounting, Research & Management Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-87)

This major group is broader than engineering consulting: it also covers accounting, scientific research and management services. Select service-specific qualifications and project metrics; do not impose an engineering backlog metric on an audit-only practice.

| Industry-Specific Facets               | Example Extracted Text / Value                                                                       |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Professional-service specialty         | • Engineering design • Accounting • Scientific research                                              |
| Engagement / delivery model            | • Fixed-scope engineering project • Recurring audit engagement • Consulting retainer                 |
| Billable utilization                   | • Billable hours / available professional hours: 72% • 80% utilization for a stated staff population |
| Workforce / expertise mix              | • Licensed professional engineers • Audit partners and associates • PhD research scientists          |
| Client industry / project domain       | • Energy infrastructure clients • Financial-services audit clients • Biotechnology research sponsors |
| Contracted work backlog                | • $500 million signed project backlog • 12 months of contracted engineering work                     |
| Professional liability / accreditation | • Professional indemnity cover • Named professional licenses • Laboratory accreditation              |

### SIC 88 — Private Households

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-88)

REFERENCE ONLY: the classified establishment is a private household employing domestic workers, not a listed domestic-service provider. A cleaning agency or care provider must be routed by its own operating activity. [Official boundary](https://www.osha.gov/data/sic-manual/major-group-88).

| Industry-Specific Facets         | Example Extracted Text / Value                                                           |
| -------------------------------- | ---------------------------------------------------------------------------------------- |
| Household employment activity    | • Household cook • Nanny • Domestic caretaker                                            |
| Employment arrangement           | • Direct household employment • Live-in domestic employment • Part-time household worker |
| Domestic staffing scale          | • Two full-time household employees • One live-in caretaker                              |
| Service / working schedule       | • Five scheduled days/week • Part-time weekly cleaning • Overnight care shifts           |
| Occupation-specific requirements | • Child-care experience • Cooking responsibilities • Property-care skills                |

### SIC 89 — Miscellaneous Services

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-89)

A residual services category, not a fallback for every unfamiliar business. Verify detailed activity against 8999 and re-route to a more specific group when evidence supports it. [Official scope](https://www.osha.gov/data/sic-manual/major-group-89).

| Industry-Specific Facets          | Example Extracted Text / Value                                                         |
| --------------------------------- | -------------------------------------------------------------------------------------- |
| Miscellaneous-service specialty   | • Independent author • Lecturer • Professional writer                                  |
| Work / delivery form              | • Commissioned manuscript • Speaking engagement • Independently produced literary work |
| Engagement / payment structure    | • Fee per lecture • Fixed manuscript fee • Royalty-bearing work                        |
| Creator / professional dependence | • Principal-author-led work • Small specialist creative team                           |
| Rights / professional constraints | • Copyright ownership • Publication rights agreement • Contractual confidentiality     |

## J. Public Administration and Nonclassifiable Reference Entries

### SIC 91 — Executive, Legislative and General Government, Except Finance

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-91)

REFERENCE ONLY: public-administration activity, not a normal listed operating-company comp template. Government ownership, government customers or a public contract alone do not put a commercial operator in this group. Route a contractor by the actual products/services it supplies.

| Industry-Specific Facets       | Example Extracted Text / Value                                                          |
| ------------------------------ | --------------------------------------------------------------------------------------- |
| Government level               | • Municipal government • State government • Federal administration                      |
| Public administrative function | • Executive administration • Legislative administration • General public administration |
| Budget / funding source        | • Tax-funded appropriation • Intergovernmental transfers • Administrative service fees  |
| Administrative jurisdiction    | • Named municipality • Named state • National jurisdiction                              |

### SIC 92 — Justice, Public Order & Safety

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-92)

REFERENCE ONLY: public-administration activity, not a normal listed operating-company comp template. Government ownership, government customers or a public contract alone do not put a commercial operator in this group. Route a contractor by the actual products/services it supplies.

| Industry-Specific Facets         | Example Extracted Text / Value                                                               |
| -------------------------------- | -------------------------------------------------------------------------------------------- |
| Justice / public-safety function | • Courts • Police services • Fire protection                                                 |
| Service jurisdiction             | • County court district • City fire-protection district • National correctional jurisdiction |
| Relevant public-service capacity | • 12 fire stations • 500 correctional beds • 20 courtrooms                                   |
| Government funding               | • County appropriations • State justice budget • Federal program grants                      |

### SIC 93 — Public Finance, Taxation & Monetary Policy

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-93)

REFERENCE ONLY: public-administration activity, not a normal listed operating-company comp template. Government ownership, government customers or a public contract alone do not put a commercial operator in this group. Route a contractor by the actual products/services it supplies.

| Industry-Specific Facets           | Example Extracted Text / Value                                                           |
| ---------------------------------- | ---------------------------------------------------------------------------------------- |
| Public-finance / monetary function | • Tax administration • Treasury operations • Monetary policy administration              |
| Public revenue / funding mechanism | • Tax receipts • Legislative appropriations • Treasury administrative fees               |
| Budget / fiscal authority          | • National treasury • State revenue department • Municipal finance authority             |
| Monetary / fiscal responsibility   | • Central monetary authority • Tax-collection authority • Government budgeting authority |

### SIC 94 — Administration of Human Resource Programs

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-94)

REFERENCE ONLY: public-administration activity, not a normal listed operating-company comp template. Government ownership, government customers or a public contract alone do not put a commercial operator in this group. Route a contractor by the actual products/services it supplies.

| Industry-Specific Facets              | Example Extracted Text / Value                                                                          |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Human-resource program administration | • Public education administration • Public health administration • Employment-program administration    |
| Covered population                    | • Eligible unemployed workers • Public-school students • Eligible benefit recipients                    |
| Public-program funding                | • Payroll-tax-funded benefit program • General-budget appropriation • Intergovernmental grant           |
| Eligibility / administrative mandate  | • Statutory work-history criteria • Means-tested program eligibility • Defined public education mandate |

### SIC 95 — Administration of Environmental Quality and Housing Programs

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-95)

REFERENCE ONLY: public-administration activity, not a normal listed operating-company comp template. Government ownership, government customers or a public contract alone do not put a commercial operator in this group. Route a contractor by the actual products/services it supplies.

| Industry-Specific Facets                        | Example Extracted Text / Value                                                             |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Environmental / housing administrative function | • Air-quality oversight • Housing-program administration • Conservation administration     |
| Public program / mandate                        | • Water-quality permitting • Public-housing administration • Wildlife-conservation program |
| Administrative jurisdiction                     | • State environmental agency • Municipal housing authority • National conservation agency  |
| Program funding source                          | • Legislative appropriations • Permit fees • Intergovernmental grants                      |

### SIC 96 — Administration of Economic Programs

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-96)

REFERENCE ONLY: public-administration activity, not a normal listed operating-company comp template. Government ownership, government customers or a public contract alone do not put a commercial operator in this group. Route a contractor by the actual products/services it supplies.

| Industry-Specific Facets        | Example Extracted Text / Value                                                                                |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Economic-program administration | • Transport-program administration • Agricultural-program administration • Business-regulation administration |
| Industry / program coverage     | • Commercial transport regulation • Agricultural development • Energy-resource administration                 |
| Grant / loan / permit authority | • Statutory grant-awarding power • Public loan-program administration • Industry permitting authority         |
| Public regulatory mandate       | • Transport licensing • Agricultural market administration • Economic-development mandate                     |

### SIC 97 — National Security & International Affairs

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-97)

REFERENCE ONLY: public-administration activity, not a normal listed operating-company comp template. Government ownership, government customers or a public contract alone do not put a commercial operator in this group. Route a contractor by the actual products/services it supplies.

| Industry-Specific Facets                   | Example Extracted Text / Value                                                                       |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| National-security / international function | • National defense administration • Diplomatic service • International affairs administration        |
| Government jurisdiction                    | • National defense authority • Foreign affairs ministry                                              |
| Procurement / operating responsibilities   | • Military procurement administration • Embassy services • International assistance administration   |
| Public budget source                       | • Defense appropriation • Foreign affairs appropriation • Authorized international assistance budget |

### SIC 99 — Nonclassifiable Establishments

[Official SIC scope](https://www.osha.gov/data/sic-manual/major-group-99)

CLASSIFICATION REVIEW ONLY. Keep unknown/nonclassifiable records visible, but do not treat all SIC 99 companies as an economic peer group. A proposed code is an analyst hypothesis until verified.

| Industry-Specific Facets            | Example Extracted Text / Value                                                                             |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Source classification status        | • SIC 9999 supplied by source • Unclassified SIC label • Missing detail-level classification               |
| Reason classification is unresolved | • Insufficient activity disclosure • Conflicting provider classifications • New operating business         |
| Proposed industry hypothesis        | • Possible SIC 7372, unconfirmed • Possible SIC 7311, unconfirmed                                          |
| Classification review disposition   | • Source verified but no industry assigned • Awaiting business description • Escalated for industry review |
