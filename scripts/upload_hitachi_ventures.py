#!/usr/bin/env python3
"""
Upload Hitachi Ventures portfolio (~48 companies) to Supabase.
Fund: Hitachi Ventures | AUM: $1B

Usage:
  python scripts/upload_hitachi_ventures.py

Requires NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.local
"""

import os
import sys
import json
from pathlib import Path

# Load env from repo root
_repo_root = Path(__file__).resolve().parents[1]
for env_file in (".env.local", ".env"):
    p = _repo_root / env_file
    if p.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(p, override=True)
            break
        except ImportError:
            pass

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or use .env.local).")
    sys.exit(1)

from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ---------------------------------------------------------------------------
# Hitachi Ventures Portfolio — cleaned from website scrape
# ---------------------------------------------------------------------------

FUND_NAME = "Hitachi Ventures"
FUND_AUM_MILLIONS = 1000  # $1B

COMPANIES = [
    {
        "name": "Aalo Atomics",
        "description": "Factory-fabricated extra-modular nuclear reactors that can be stacked together, designed to decarbonize anything from small data centers to cities with affordable clean energy.",
        "sectors": ["Environment", "Industrial"],
        "stage": "Series A",
        "hq": "Texas",
        "ceo": "Matt Loszak",
        "deal_team": ["Pete Bastien", "Matt Morris", "Grace Mathis"],
    },
    {
        "name": "Akarion",
        "description": "Blockchain-based software for EU GDPR compliance and data-security management.",
        "sectors": ["Digital"],
        "stage": "Seed",
        "hq": "Germany",
        "ceo": "Philipp Aman",
        "deal_team": [],
    },
    {
        "name": "Amplio",
        "description": "AI-enabled marketplace for manufacturers to sell industrial surplus inventory at fair market prices, helping buyers access discounted essential parts.",
        "sectors": ["Environment", "Industrial"],
        "stage": "Series A",
        "hq": "Georgia",
        "ceo": "Trey Closson",
        "deal_team": ["Pete Bastien", "Grace Mathis", "Matt Morris", "Somil Singh"],
    },
    {
        "name": "Arcee AI",
        "description": "Builds efficient small language models and agentic workflow automation for domain-specific AI in finance, healthcare, and legal.",
        "sectors": ["Digital"],
        "stage": "Series A",
        "hq": "California",
        "ceo": "Mark McQuade",
        "deal_team": ["Gayathri Radhakrishnan", "Aditi Purandare", "Pratik Malhotra"],
    },
    {
        "name": "Archetype AI",
        "description": "Develops Newton, a multimodal AI foundation model that fuses real-time sensor data with natural language to understand the physical world.",
        "sectors": ["Digital", "Industrial"],
        "stage": "Seed",
        "hq": "California",
        "ceo": "Ivan Poupyrev",
        "deal_team": ["Gayathri Radhakrishnan", "Galina Sagan", "Vamsi Patti"],
    },
    {
        "name": "Arrcus",
        "description": "Software-defined network OS with programmable control and data plane for datacenter, edge, telco, and multi/hybrid cloud environments.",
        "sectors": ["Digital"],
        "stage": "Series D",
        "hq": "California",
        "ceo": "Shekar Ayyar",
        "deal_team": ["Gayathri Radhakrishnan", "Galina Sagan", "Vamsi Patti"],
    },
    {
        "name": "Arsenal Bio",
        "description": "Develops programmable CAR-T cell therapies using genetic circuits, CRISPR, AI, and data analytics to treat solid tumors.",
        "sectors": ["Healthcare"],
        "stage": "Series C",
        "hq": "California",
        "ceo": "Ken Drazan",
        "deal_team": ["Wolfgang Seibold", "Joanna Soroka"],
    },
    {
        "name": "Ascend Elements",
        "description": "EV battery recycling to commercial-scale production of lithium carbonate, NMC precursor, and cathode active materials for sustainable closed-loop battery supply chain.",
        "sectors": ["Environment", "Industrial"],
        "stage": "Series D",
        "hq": "Massachusetts",
        "ceo": "Mike O'Kronley",
        "deal_team": ["Tobias Jahn", "Galina Sagan", "Jan Marchewski"],
    },
    {
        "name": "Avicena",
        "description": "Develops ultra-low power micro-LED interconnects for AI chip connectivity in data centers.",
        "sectors": ["Digital"],
        "stage": "Series B",
        "hq": "California",
        "ceo": "Marco Chisari",
        "deal_team": ["Gayathri Radhakrishnan", "Vamsi Patti", "Aditi Purandare"],
    },
    {
        "name": "BeZero Carbon",
        "description": "Ratings agency and risk analytics for the global voluntary carbon market, providing carbon credit quality ratings to institutional buyers.",
        "sectors": ["Environment"],
        "stage": "Series B",
        "hq": "London",
        "ceo": "Tommy Ricketts",
        "deal_team": ["Tobias Jahn", "Galina Sagan", "Jan Marchewski"],
    },
    {
        "name": "Bioptimus",
        "description": "Building the first universal multi-scale, multi-modal foundation model for biology to uncover relationships across biological systems for biomedicine research.",
        "sectors": ["Digital", "Healthcare"],
        "stage": "Series A",
        "hq": "Paris",
        "ceo": "Jean-Philippe Vert",
        "deal_team": ["Wolfgang Seibold", "Joanna Soroka", "Marina Du", "Aditi Purandare"],
    },
    {
        "name": "Captura",
        "description": "Direct Ocean Capture technology that removes CO2 from seawater using proprietary electrodialysis, powered by renewable energy, producing pure CO2 for sequestration.",
        "sectors": ["Environment"],
        "stage": "Series A",
        "hq": "California",
        "ceo": "Steve Oldham",
        "deal_team": ["Pete Bastien", "Jan Marchewski"],
    },
    {
        "name": "Cure51",
        "description": "Building the first global clinical and molecular database of cancer survivors to identify therapeutic targets and uncover new life-saving medicines.",
        "sectors": ["Healthcare"],
        "stage": "Seed",
        "hq": "Paris",
        "ceo": "Nicolas Wolikow",
        "deal_team": ["Wolfgang Seibold", "Joanna Soroka", "Marina Du"],
    },
    {
        "name": "CVector",
        "description": "Industrial AI platform that maps industrial data in real-time, enabling agents to give microsecond recommendations for critical asset environments grounded in physical simulations.",
        "sectors": ["Industrial"],
        "stage": "Seed",
        "hq": "New York",
        "ceo": None,
        "deal_team": ["Tobias Jahn", "Edoardo Stazio"],
    },
    {
        "name": "Cyclic Materials",
        "description": "Creates circular supply chain for rare earth elements through economic and sustainable magnet recycling from end-of-life products.",
        "sectors": ["Environment"],
        "stage": "Series B",
        "hq": "Ontario",
        "ceo": "Ahmad Ghahreman",
        "deal_team": ["Tobias Jahn", "Jan Marchewski", "Elena Ballesteros"],
    },
    {
        "name": "Edgescale AI",
        "description": "Software-defined edge platform that runs on industrial edge hardware, managing AI, data, and lifecycle across fleets of physical sites for manufacturing and utilities.",
        "sectors": ["Industrial"],
        "stage": "Series A",
        "hq": "Denver, Colorado",
        "ceo": "Brian Mengwasser",
        "deal_team": ["Jan Marchewski", "Gayathri Radhakrishnan"],
    },
    {
        "name": "Ema",
        "description": "Builds universal AI employees that can take on any enterprise role from customer support to legal and compliance, automating mundane tasks.",
        "sectors": ["Digital"],
        "stage": "Series A",
        "hq": "California",
        "ceo": "Surojit Chatterjee",
        "deal_team": ["Gayathri Radhakrishnan", "Aditi Purandare"],
    },
    {
        "name": "Equiem",
        "description": "Smart building management platform integrating building operations, flexible space management, and tenant engagement for real estate owners and operators.",
        "sectors": ["Digital", "Industrial"],
        "stage": "Series B",
        "hq": "Melbourne",
        "ceo": "Gabrielle McMillan",
        "deal_team": ["Tobias Jahn"],
    },
    {
        "name": "Grow Inc",
        "description": "Wealth administration platform providing technology and services to superannuation funds and fund managers in Australia for member records, workflows, and calculations.",
        "sectors": ["Digital"],
        "stage": "Series D",
        "hq": "Sydney",
        "ceo": "Mathew Keeley",
        "deal_team": ["Wolfgang Seibold", "Galina Sagan", "Elena Ballesteros"],
    },
    {
        "name": "Huma",
        "description": "Digital health platform enabling Hospital at Home with remote patient monitoring, companion apps for pharma/medtech, and digital clinical trial deployment.",
        "sectors": ["Digital", "Healthcare"],
        "stage": "Series D",
        "hq": "London",
        "ceo": "Dan Vahdat",
        "deal_team": ["Wolfgang Seibold"],
    },
    {
        "name": "Infravision",
        "description": "Integrated aerial robotics platform with custom drones and electric tensioner unit that automates power line stringing for grid capacity expansion.",
        "sectors": ["Environment"],
        "stage": "Series B",
        "hq": None,
        "ceo": "Cameron Van Der Berg",
        "deal_team": ["Pete Bastien", "Grace Mathis", "Matt Morris", "Somil Singh", "Tobias Graf"],
    },
    {
        "name": "inVia Robotics",
        "description": "Autonomous mobile robots and AI-driven warehouse automation with Goods-to-Person systems for e-commerce fulfillment and distribution centers.",
        "sectors": ["Industrial"],
        "stage": "Series C",
        "hq": "California",
        "ceo": "Lior Elazary",
        "deal_team": ["Pete Bastien"],
    },
    {
        "name": "iPeace",
        "description": "Fully automated mass production of induced pluripotent stem cells using advanced robotics and fluidics, providing research-grade and clinical-grade iPSCs.",
        "sectors": ["Healthcare"],
        "stage": "Series B",
        "hq": "California",
        "ceo": "Koji Tanabe",
        "deal_team": [],
    },
    {
        "name": "Lineaje",
        "description": "Software supply chain security platform providing continuous SBOM management, detecting supply chain attacks across applications built or bought by enterprises.",
        "sectors": ["Digital"],
        "stage": "Series A",
        "hq": "California",
        "ceo": "Javed Hasan",
        "deal_team": ["Gayathri Radhakrishnan", "Galina Sagan", "Tobias Graf", "Aditi Purandare"],
    },
    {
        "name": "Makersite",
        "description": "Product lifecycle intelligence platform combining manufacturer data with 140 material/process/supplier databases to create digital twins for sustainable product decisions.",
        "sectors": ["Environment"],
        "stage": "Series A",
        "hq": "Stuttgart, Germany",
        "ceo": "Neil D'Souza",
        "deal_team": ["Tobias Jahn", "Galina Sagan", "Jan Marchewski"],
    },
    {
        "name": "NovoLINC",
        "description": "Develops nanostructured copper thermal interface materials to enhance heat transfer from high-performance AI chips in data centers.",
        "sectors": ["Digital"],
        "stage": "Seed",
        "hq": "Pittsburgh",
        "ceo": "Ning Li",
        "deal_team": ["Wolfgang Seibold", "Vamsi Patti", "Pratik Malhotra"],
    },
    {
        "name": "Opsera",
        "description": "Unified DevOps lifecycle platform providing single-pane visibility across SDLC, SaaS apps, data and analytics, and security.",
        "sectors": ["Digital"],
        "stage": "Series B",
        "hq": "California",
        "ceo": "Kumar Chivukula",
        "deal_team": ["Gayathri Radhakrishnan", "Galina Sagan", "Aditi Purandare"],
    },
    {
        "name": "Pantomath",
        "description": "Automated data operations platform unifying real-time monitoring, cross-platform lineage, and AI-driven root-cause and impact analysis.",
        "sectors": ["Digital"],
        "stage": "Series B",
        "hq": None,
        "ceo": "Shashank Saxena",
        "deal_team": ["Gayathri Radhakrishnan", "Aditi Purandare", "Tobias Graf"],
    },
    {
        "name": "Pow.Bio",
        "description": "AI-controlled continuous fermentation bioreactors enabling uninterrupted biomanufacturing of organic acids and food proteins with consistent quality.",
        "sectors": ["Industrial"],
        "stage": "Series A",
        "hq": "Berkeley, California",
        "ceo": "Shannon Hall",
        "deal_team": ["Pete Bastien", "Matt Morris"],
    },
    {
        "name": "Proscia",
        "description": "AI-powered digital pathology platform for biopharma R&D, CRO tissue analysis, and diagnostic lab collaboration through the Concentriq system.",
        "sectors": ["Healthcare"],
        "stage": "Series C",
        "hq": "Pennsylvania",
        "ceo": "David West",
        "deal_team": ["Pete Bastien", "Joanna Soroka"],
    },
    {
        "name": "Provectus Algae",
        "description": "Uses Precision Photosynthesis process to produce Asparagopsis algae-based feed additive that cuts livestock methane emissions by up to 95%.",
        "sectors": ["Environment", "Industrial"],
        "stage": "Pre-Series A",
        "hq": "Australia",
        "ceo": "Nusqe Spanton",
        "deal_team": ["Pete Bastien"],
    },
    {
        "name": "Regrello",
        "description": "AI-powered supply chain manager combining traditional and generative AI to automate end-to-end manufacturing operations and back-office workflows.",
        "sectors": ["Digital", "Industrial"],
        "stage": "Series A",
        "hq": "California",
        "ceo": "Aman Naimat",
        "deal_team": ["Wolfgang Seibold", "Jan Marchewski", "Pratik Malhotra"],
        "exited": True,
        "exit_date": "2025-10",
    },
    {
        "name": "RegScale",
        "description": "Compliance-as-code platform that automates evidence collection and control monitoring in real-time, replacing manual GRC audits across NIST, ISO, and GDPR frameworks.",
        "sectors": ["Digital", "Industrial"],
        "stage": "Series B",
        "hq": "Virginia",
        "ceo": "Travis Howerton",
        "deal_team": ["Tobias Graf", "Galina Sagan"],
    },
    {
        "name": "Relation Therapeutics",
        "description": "Drug discovery company combining ActiveGraph AI models with Lab-in-the-Loop for single-cell analysis at scale, building disease maps to identify novel drug targets.",
        "sectors": ["Digital", "Healthcare"],
        "stage": "Seed",
        "hq": "London",
        "ceo": "David Roblin",
        "deal_team": ["Wolfgang Seibold", "Joanna Soroka", "Marina Du"],
    },
    {
        "name": "Rescale",
        "description": "Cloud-based hybrid compute platform for scientific and engineering simulations, providing infinite scale and workload-optimized HPC infrastructure.",
        "sectors": ["Digital"],
        "stage": "Series C",
        "hq": "California",
        "ceo": "Joris Poort",
        "deal_team": ["Wolfgang Seibold", "Galina Sagan"],
    },
    {
        "name": "Samsara Eco",
        "description": "Enzymatic technology that breaks down plastic waste into core molecules in minutes regardless of type, color, or state for infinite recycling.",
        "sectors": ["Environment"],
        "stage": "Series A",
        "hq": "Sydney",
        "ceo": "Paul Riley",
        "deal_team": ["Tobias Jahn", "Jan Marchewski"],
    },
    {
        "name": "Scipher Medicine",
        "description": "Uses transcriptomics and network biology to uncover molecular disease signatures in autoimmune patients, advancing diagnostics, drug discovery, and personalized treatment.",
        "sectors": ["Healthcare"],
        "stage": "Series D",
        "hq": "Massachusetts",
        "ceo": "Reginald Seeto",
        "deal_team": ["Wolfgang Seibold", "Joanna Soroka"],
    },
    {
        "name": "Sophia Genetics",
        "description": "Decentralized AI-driven data analytics platform integrating genomics, radiology, and clinical data across 750+ global health institutions for precision medicine.",
        "sectors": ["Healthcare"],
        "stage": "Exited",
        "hq": "Massachusetts",
        "ceo": "Jurgi Camblong",
        "deal_team": ["Wolfgang Seibold"],
        "exited": True,
    },
    {
        "name": "Strangeworks",
        "description": "Hybrid compute platform providing unified access to any quantum machine on the market, enabling custom quantum IP development and algorithm benchmarking.",
        "sectors": ["Digital"],
        "stage": "Series A",
        "hq": "Texas",
        "ceo": "Whurley",
        "deal_team": ["Tobias Jahn"],
    },
    {
        "name": "StrikeReady",
        "description": "AI-powered cybersecurity command center combining SIEM, SOAR, and workflow automation with agent-based assistance for security operations centers.",
        "sectors": ["Digital"],
        "stage": "Series A",
        "hq": "Texas",
        "ceo": "Yasir Khalid",
        "deal_team": ["Wolfgang Seibold", "Galina Sagan", "Tobias Graf"],
    },
    {
        "name": "Taranis",
        "description": "Uses computer vision and deep learning on aerial imagery to detect early symptoms of weeds, disease, nutrient deficiencies, and insect infestations in crops.",
        "sectors": ["Digital", "Environment"],
        "stage": "Series D",
        "hq": "California",
        "ceo": "Opher Flohr",
        "deal_team": ["Wolfgang Seibold", "Galina Sagan"],
    },
    {
        "name": "Teramount",
        "description": "Develops self-aligning, detachable fiber-to-chip optical connectors using patented Universal Photonic Coupler for AI, data center, and telecom applications.",
        "sectors": ["Digital"],
        "stage": "Series A",
        "hq": None,
        "ceo": "Hesham Taha",
        "deal_team": ["Gayathri Radhakrishnan", "Vamsi Patti", "Pratik Malhotra"],
    },
    {
        "name": "Thea Energy",
        "description": "Planar coil stellarator design using arrays of planar magnets for manufacturing and dynamically controlling stellarators to achieve cost-competitive commercial fusion.",
        "sectors": ["Environment"],
        "stage": "Series A",
        "hq": "Texas",
        "ceo": "Brian Berzin",
        "deal_team": ["Wolfgang Seibold", "Tobias Jahn", "Elena Ballesteros", "Tobias Graf"],
    },
    {
        "name": "Tibo Energy",
        "description": "AI-driven cloud-native Energy Management System that simulates and optimises local energy use across solar, batteries, and EV chargers for commercial/industrial sites.",
        "sectors": ["Digital", "Environment"],
        "stage": "Seed",
        "hq": None,
        "ceo": "Remco Eikhout",
        "deal_team": ["Tobias Jahn", "Elena Ballesteros", "Edoardo Stazio"],
    },
    {
        "name": "Trustwise",
        "description": "Provides NIM microservices via single API to accelerate development of trustworthy GenAI systems while reducing operational costs and carbon emissions.",
        "sectors": ["Digital"],
        "stage": "Seed",
        "hq": "Texas",
        "ceo": "Manoj Saxena",
        "deal_team": ["Gayathri Radhakrishnan", "Galina Sagan", "Vamsi Patti"],
    },
    {
        "name": "WASE",
        "description": "Electro-Methanogenic Reactor using proprietary membrane-less electrode technology with biofilm to break down diverse waste streams, generating methane-rich biogas.",
        "sectors": ["Environment"],
        "stage": "Seed",
        "hq": "Bristol",
        "ceo": "Thomas Fudge",
        "deal_team": ["Tobias Jahn", "Elena Ballesteros", "Grace Mathis"],
    },
    {
        "name": "WEKA",
        "description": "Software-defined hybrid cloud data platform for high-performance computing, AI, and ML workloads, transforming data silos into dynamic data pipelines.",
        "sectors": ["Digital"],
        "stage": "Series E",
        "hq": "California",
        "ceo": "Liran Zvibel",
        "deal_team": ["Pete Bastien", "Galina Sagan"],
    },
    {
        "name": "Xaba",
        "description": "AI-powered software using digital twins and physics AI to automate industrial robotic systems for manufacturing and construction with minimal human oversight.",
        "sectors": ["Digital", "Industrial"],
        "stage": "Seed",
        "hq": "Ontario",
        "ceo": "Massimiliano Moruzzi",
        "deal_team": ["Gayathri Radhakrishnan", "Vamsi Patti"],
    },
]

# ---------------------------------------------------------------------------
# Stage mapping
# ---------------------------------------------------------------------------
STAGE_MAP = {
    "Seed": "portfolio",
    "Pre-Series A": "portfolio",
    "Series A": "portfolio",
    "Series B": "portfolio",
    "Series C": "portfolio",
    "Series D": "portfolio",
    "Series E": "portfolio",
    "Stage +": "portfolio",
    "Exited": "portfolio",  # still use portfolio; mark exited in extra_data
}


def create_or_get_fund() -> str:
    """Create Hitachi Ventures fund or return existing ID."""
    # Check if fund already exists
    result = supabase.table("funds").select("id").ilike("name", f"%{FUND_NAME}%").execute()
    if result.data:
        fund_id = result.data[0]["id"]
        print(f"Found existing fund: {FUND_NAME} (id={fund_id})")
        return fund_id

    # Create new fund
    payload = {
        "name": FUND_NAME,
        "fund_size_usd": FUND_AUM_MILLIONS,
        "fund_type": "venture",
        "status": "active",
    }
    result = supabase.table("funds").insert(payload).execute()
    if result.data:
        fund_id = result.data[0]["id"]
        print(f"Created fund: {FUND_NAME} (id={fund_id}, AUM=${FUND_AUM_MILLIONS}M)")
        return fund_id
    else:
        print(f"Failed to create fund: {result}")
        sys.exit(1)


def upload_companies(fund_id: str) -> None:
    """Upload all portfolio companies."""
    inserted = 0
    skipped = 0
    errors = 0

    for co in COMPANIES:
        is_exited = co.get("exited", False)

        extra_data = {
            "sectors": co["sectors"],
            "investment_stage": co["stage"],
            "deal_team": co["deal_team"],
            "fund_name": FUND_NAME,
            "source": "hitachi_ventures_website",
        }
        if co.get("ceo"):
            extra_data["ceo"] = co["ceo"]
        if is_exited:
            extra_data["exited"] = True
            extra_data["exit_date"] = co.get("exit_date")

        payload = {
            "name": co["name"],
            "fund_id": fund_id,
            "funnel_status": "portfolio",
            "status": "exited" if is_exited else "active",
            "description": co["description"],
            "sector": co["sectors"][0] if co["sectors"] else None,
            "funding_stage": co["stage"],
            "headquarters": co.get("hq"),
            "total_invested_usd": 1,  # placeholder — no check sizes in source data
            "extra_data": extra_data,
        }

        try:
            result = supabase.table("companies").insert(payload).execute()
            if result.data:
                inserted += 1
                status_tag = " [EXITED]" if is_exited else ""
                print(f"  OK: {co['name']}{status_tag} ({co['stage']}, {co['sectors']})")
            else:
                errors += 1
                print(f"  FAIL (no data): {co['name']}")
        except Exception as e:
            msg = str(e).lower()
            if "23505" in msg or "duplicate" in msg or "unique" in msg:
                skipped += 1
                print(f"  SKIP (exists): {co['name']}")
            else:
                errors += 1
                print(f"  ERROR: {co['name']} -> {e}")

    print(f"\n{'='*60}")
    print(f"Hitachi Ventures Portfolio Upload Complete")
    print(f"{'='*60}")
    print(f"  Total companies: {len(COMPANIES)}")
    print(f"  Inserted:        {inserted}")
    print(f"  Skipped (dupes): {skipped}")
    print(f"  Errors:          {errors}")
    print(f"{'='*60}")

    # Print sector breakdown
    sector_counts: dict[str, int] = {}
    stage_counts: dict[str, int] = {}
    for co in COMPANIES:
        for s in co["sectors"]:
            sector_counts[s] = sector_counts.get(s, 0) + 1
        stage_counts[co["stage"]] = stage_counts.get(co["stage"], 0) + 1

    print(f"\nSector Breakdown:")
    for s, c in sorted(sector_counts.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")

    print(f"\nStage Breakdown:")
    for s, c in sorted(stage_counts.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")


if __name__ == "__main__":
    print(f"Uploading {len(COMPANIES)} companies for {FUND_NAME} (${FUND_AUM_MILLIONS/1000:.0f}B AUM)")
    print(f"Supabase: {SUPABASE_URL}")
    print()

    fund_id = create_or_get_fund()
    print()
    upload_companies(fund_id)
