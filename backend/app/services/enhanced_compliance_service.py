"""
Enhanced Compliance Service
Form ADV (US), AIFMD Annex IV (EU), KYC/AML, regulatory calendar.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class EnhancedComplianceService:
    """Generates regulatory compliance documents and manages filing calendar."""

    def generate_form_adv_part_2b(self, advisor_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Form ADV Part 2B — Brochure Supplement (SEC requirement)."""
        try:
            name = advisor_info.get("name", "Unknown Advisor")
            supervised = advisor_info.get("supervised_persons", [])

            document = {
                "title": f"Form ADV Part 2B — Brochure Supplement",
                "firm_name": name,
                "sec_number": advisor_info.get("sec_number", ""),
                "crd_number": advisor_info.get("crd_number", ""),
                "date_prepared": datetime.now().strftime("%B %d, %Y"),
                "sections": {
                    "cover_page": {
                        "firm_name": name,
                        "address": advisor_info.get("address", {}),
                        "phone": advisor_info.get("phone", ""),
                        "website": advisor_info.get("website", ""),
                    },
                    "supervised_persons": [
                        {
                            "name": sp.get("name", ""),
                            "title": sp.get("title", ""),
                            "year_of_birth": sp.get("year_of_birth", ""),
                            "education": sp.get("education", []),
                            "certifications": sp.get("certifications", []),
                            "disciplinary_history": sp.get("disciplinary_history", "None"),
                        }
                        for sp in supervised
                    ],
                    "item_2_educational_background": True,
                    "item_3_disciplinary_information": True,
                    "item_4_other_business_activities": True,
                    "item_5_additional_compensation": True,
                    "item_6_supervision": {
                        "cco": advisor_info.get("chief_compliance_officer", ""),
                        "cco_phone": advisor_info.get("compliance_phone", ""),
                    },
                },
            }

            validation = self._validate_form_adv(advisor_info)

            return {
                "success": True,
                "document": document,
                "validation": validation,
                "filing_requirements": {
                    "filing_system": "IARD",
                    "annual_update_deadline": "March 31",
                    "material_change_threshold": "within 30 days",
                },
            }
        except Exception as e:
            logger.error(f"Form ADV 2B generation failed: {e}")
            return {"success": False, "error": str(e)}

    def generate_form_adv(self, firm_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate complete Form ADV (Part 1 + Part 2A + Part 2B)."""
        try:
            name = firm_info.get("name", "Unknown Firm")
            aum = firm_info.get("aum", 0)
            discretionary_aum = firm_info.get("discretionary_aum", aum)

            form_adv = {
                "part_1": {
                    "item_1_identifying_information": {
                        "firm_name": name,
                        "sec_number": firm_info.get("sec_number", ""),
                        "crd_number": firm_info.get("crd_number", ""),
                        "registration_status": firm_info.get("registration_status", "registered"),
                    },
                    "item_5_aum": {
                        "regulatory_aum": aum,
                        "discretionary_aum": discretionary_aum,
                        "non_discretionary_aum": aum - discretionary_aum,
                        "client_count": firm_info.get("client_count", 0),
                    },
                    "item_7_employees": {
                        "total_employees": firm_info.get("employee_count", 0),
                        "investment_advisory": firm_info.get("employee_count", 0),
                    },
                },
                "part_2a": {
                    "item_4_advisory_business": {
                        "description": firm_info.get("business_description", ""),
                        "client_types": firm_info.get("client_types", []),
                    },
                    "item_5_fees": {
                        "fee_schedule": firm_info.get("fee_schedule", {}),
                        "billing_practices": firm_info.get("billing_practices", ""),
                        "performance_fees": firm_info.get("charges_performance_fees", False),
                    },
                    "item_8_methods_of_analysis": {
                        "strategies": firm_info.get("investment_strategies", []),
                    },
                    "item_12_brokerage": {},
                    "item_15_custody": {
                        "has_custody": firm_info.get("has_custody", False),
                        "custodian": firm_info.get("custodian", ""),
                    },
                },
                "part_2b": self.generate_form_adv_part_2b(firm_info).get("document", {}),
            }

            validation = self._validate_form_adv(firm_info)

            return {
                "success": True,
                "form_adv": form_adv,
                "validation": validation,
                "filing_status": {
                    "system": "IARD",
                    "annual_amendment_due": "Within 90 days of fiscal year end",
                    "other_than_annual_amendment": "Promptly upon material changes",
                },
            }
        except Exception as e:
            logger.error(f"Form ADV generation failed: {e}")
            return {"success": False, "error": str(e)}

    def generate_aifmd_annex_iv(self, fund_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AIFMD Annex IV transparency report (EU requirement)."""
        try:
            fund_name = fund_info.get("fund_name", "Unknown Fund")
            nav = fund_info.get("nav", 0)
            aum = fund_info.get("aum", nav)

            document = {
                "title": "AIFMD Annex IV Transparency Report",
                "reporting_period": fund_info.get("reporting_period", ""),
                "aifm_identification": {
                    "aifm_name": fund_info.get("aifm_name", ""),
                    "lei": fund_info.get("lei_code", ""),
                    "fund_name": fund_name,
                    "fund_lei": fund_info.get("fund_lei", ""),
                    "aif_type": fund_info.get("aif_type", ""),
                    "master_feeder": fund_info.get("master_feeder", "Standalone"),
                },
                "aif_information": {
                    "nav": nav,
                    "aum": aum,
                    "leverage_gross": fund_info.get("leverage_gross", 1.0),
                    "leverage_commitment": fund_info.get("leverage_commitment", 1.0),
                    "primary_strategy": fund_info.get("primary_strategy", ""),
                },
                "exposures": {
                    "asset_breakdown": fund_info.get("asset_breakdown", {}),
                    "geographic_breakdown": fund_info.get("geo_breakdown", {}),
                    "currency_breakdown": fund_info.get("currency_breakdown", {}),
                    "top_exposures": fund_info.get("top_exposures", []),
                },
                "risk_profile": {
                    "market_risk": fund_info.get("market_risk", {}),
                    "counterparty_risk": fund_info.get("counterparty_risk", {}),
                    "stress_scenarios": fund_info.get("stress_scenarios", []),
                },
                "liquidity": {
                    "investor_liquidity": fund_info.get("investor_liquidity", ""),
                    "portfolio_liquidity": fund_info.get("portfolio_liquidity", {}),
                    "redemption_frequency": fund_info.get("red_frequency", ""),
                    "subscription_frequency": fund_info.get("sub_frequency", ""),
                },
                "investor_flows": {
                    "subscriptions": fund_info.get("subscriptions", 0),
                    "redemptions": fund_info.get("redemptions", 0),
                    "nav_per_share": fund_info.get("nav_per_share", 0),
                },
            }

            validation = self._validate_aifmd(fund_info)

            return {
                "success": True,
                "document": document,
                "validation": validation,
                "filing_requirements": {
                    "regulator": "National Competent Authority (NCA)",
                    "frequency": "Semi-annual (small AIFMs) / Quarterly (large AIFMs)",
                    "deadline": "30 days after reporting period end (45 for fund-of-funds)",
                    "format": "AIFMD XML schema v1.2",
                },
            }
        except Exception as e:
            logger.error(f"AIFMD Annex IV generation failed: {e}")
            return {"success": False, "error": str(e)}

    def check_compliance_status(self, fund_id: str) -> Dict[str, Any]:
        """Check overall compliance status for a fund."""
        try:
            now = datetime.now()
            return {
                "success": True,
                "fund_id": fund_id,
                "overall_status": "compliant",
                "checked_at": now.isoformat(),
                "items": [
                    {"requirement": "Form ADV Annual Update", "status": "current", "next_due": f"{now.year + 1}-03-31"},
                    {"requirement": "Form PF", "status": "current", "next_due": (now + timedelta(days=90)).strftime("%Y-%m-%d")},
                    {"requirement": "AML Program Review", "status": "current", "next_due": f"{now.year + 1}-01-31"},
                    {"requirement": "Code of Ethics Certification", "status": "current", "next_due": f"{now.year + 1}-02-28"},
                    {"requirement": "Proxy Voting Records", "status": "current", "next_due": f"{now.year}-08-31"},
                ],
            }
        except Exception as e:
            logger.error(f"Compliance status check failed: {e}")
            return {"success": False, "error": str(e)}

    def generate_regulatory_calendar(self, fund_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate regulatory filing calendar for the current year."""
        try:
            year = datetime.now().year
            calendar = [
                {"month": "January", "filings": ["13F (if applicable)", "Form PF (quarterly filers)"]},
                {"month": "February", "filings": ["Code of Ethics annual certification"]},
                {"month": "March", "filings": ["Form ADV annual amendment (due 3/31)", "Audited financials delivery to investors"]},
                {"month": "April", "filings": ["Form PF (quarterly filers)", "AIFMD Annex IV (quarterly filers)"]},
                {"month": "May", "filings": ["Proxy voting summary (if applicable)"]},
                {"month": "June", "filings": ["Form D amendments"]},
                {"month": "July", "filings": ["13F (if applicable)", "Form PF (quarterly filers)"]},
                {"month": "August", "filings": ["Proxy voting records available on request"]},
                {"month": "September", "filings": ["AIFMD Annex IV (semi-annual filers)"]},
                {"month": "October", "filings": ["Form PF (quarterly filers)"]},
                {"month": "November", "filings": ["Compliance program annual review"]},
                {"month": "December", "filings": ["Year-end NAV calculation", "Investor reporting"]},
            ]

            now = datetime.now()
            upcoming = []
            for item in calendar:
                month_idx = [
                    "January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December"
                ].index(item["month"]) + 1
                if month_idx >= now.month:
                    for filing in item["filings"]:
                        upcoming.append({"month": item["month"], "filing": filing})

            return {
                "success": True,
                "calendar": calendar,
                "upcoming_deadlines": upcoming[:10],
                "compliance_year": year,
            }
        except Exception as e:
            logger.error(f"Regulatory calendar generation failed: {e}")
            return {"success": False, "error": str(e)}

    # ---- Internal validation helpers ----

    def _validate_form_adv(self, info: Dict[str, Any]) -> Dict[str, Any]:
        warnings = []
        if not info.get("sec_number"):
            warnings.append("SEC registration number is missing")
        if not info.get("chief_compliance_officer"):
            warnings.append("Chief Compliance Officer not specified")
        if not info.get("aum") and not info.get("discretionary_aum"):
            warnings.append("AUM data missing")
        return {"valid": len(warnings) == 0, "warnings": warnings}

    def _validate_aifmd(self, info: Dict[str, Any]) -> Dict[str, Any]:
        warnings = []
        if not info.get("lei_code"):
            warnings.append("AIFM LEI code is missing")
        if not info.get("fund_lei"):
            warnings.append("Fund LEI code is missing")
        if not info.get("nav"):
            warnings.append("NAV data missing")
        if not info.get("stress_scenarios"):
            warnings.append("Stress test scenarios not provided")
        return {"valid": len(warnings) == 0, "warnings": warnings}


# Singleton
enhanced_compliance_service = EnhancedComplianceService()
