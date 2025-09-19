"""
Pre and Post Money Cap Table Calculator
Shows ownership before and after each funding round
"""

from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, getcontext
import numpy as np

# Set precision for financial calculations
getcontext().prec = 10

@dataclass
class CapTableSnapshot:
    """Snapshot of cap table at a point in time"""
    round_name: str
    date: datetime
    pre_money_valuation: Decimal
    investment_amount: Decimal
    post_money_valuation: Decimal
    pre_money_ownership: Dict[str, Decimal]  # Ownership % before round
    post_money_ownership: Dict[str, Decimal]  # Ownership % after round
    new_investors: List[str]
    option_pool_expansion: Decimal
    
class PrePostCapTable:
    """
    Calculates pre and post money cap tables for each funding round
    Shows dilution waterfall through company history
    """
    
    # Class constants for dilution rates
    DILUTION_BY_STAGE = {
        "Pre-seed": Decimal('0.10'),
        "Seed": Decimal('0.15'),
        "Series A": Decimal('0.20'),
        "Series B": Decimal('0.18'),
        "Series C": Decimal('0.15'),
        "Series D": Decimal('0.12'),
        "Series E": Decimal('0.10')
    }
    
    LEAD_INVESTOR_SHARE = Decimal('0.6')  # Lead takes 60% of round
    OPTION_EXERCISE_RATE = Decimal('0.25')  # 75% unexercised (Carta benchmark)
    
    def __init__(self):
        self.option_exercise_rate = self.OPTION_EXERCISE_RATE
        
    def calculate_full_cap_table_history(
        self, 
        company_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate complete cap table evolution through all rounds
        Returns data structured for Sankey/waterfall visualization
        """
        
        funding_rounds = company_data.get("funding_rounds", [])
        
        # Initialize with founders owning 100%
        cap_table_history = []
        current_cap_table = {
            "Founders": Decimal('100.0')
        }
        
        # Track cumulative dilution
        cumulative_invested = Decimal('0')
        
        for i, round_data in enumerate(funding_rounds):
            round_name = round_data.get("round", f"Round {i+1}")
            amount = Decimal(str(round_data.get("amount", 0)))
            pre_money = Decimal(str(round_data.get("pre_money_valuation", 0)))
            
            # If no pre-money, estimate from amount and typical dilution
            if pre_money == 0:
                typical_dilution = self._get_typical_dilution(round_name)
                pre_money = (amount / typical_dilution - amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            post_money = pre_money + amount
            
            # Save pre-money state
            pre_money_cap_table = current_cap_table.copy()
            
            # Calculate dilution
            dilution = (amount / post_money).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            
            # Create post-money cap table efficiently
            post_money_cap_table = {}
            
            # Apply dilution to all existing shareholders at once
            dilution_factor = Decimal('1') - dilution
            for shareholder, ownership in current_cap_table.items():
                post_money_cap_table[shareholder] = (ownership * dilution_factor).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            
            # Add new investors
            investors = round_data.get("investors", [])
            lead_investor = round_data.get("lead_investor")
            round_ownership = dilution * Decimal('100')
            
            if lead_investor:
                # Lead takes 60% of round
                post_money_cap_table[f"{lead_investor} (Lead)"] = (round_ownership * self.LEAD_INVESTOR_SHARE).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
                # Others split remaining 40%
                other_investors = [i for i in investors if i != lead_investor]
                if other_investors:
                    other_stake = round_ownership * (1 - self.LEAD_INVESTOR_SHARE)
                    per_investor = other_stake / len(other_investors)
                    for investor in other_investors:
                        post_money_cap_table[investor] = per_investor
            elif investors:
                # Equal split among all investors
                per_investor = round_ownership / len(investors)
                for investor in investors:
                    post_money_cap_table[investor] = per_investor
            else:
                # Generic investor label
                post_money_cap_table[f"{round_name} Investors"] = round_ownership
            
            # Add option pool if needed
            option_pool_expansion = round_data.get("option_pool_expansion", 0)
            if option_pool_expansion > 0:
                # Option pool dilutes everyone
                for shareholder in post_money_cap_table:
                    post_money_cap_table[shareholder] *= (1 - option_pool_expansion)
                post_money_cap_table["Option Pool"] = option_pool_expansion * 100
            
            # Create snapshot
            snapshot = CapTableSnapshot(
                round_name=round_name,
                date=round_data.get("date", datetime.now()),
                pre_money_valuation=pre_money,
                investment_amount=amount,
                post_money_valuation=post_money,
                pre_money_ownership=pre_money_cap_table,
                post_money_ownership=post_money_cap_table,
                new_investors=investors,
                option_pool_expansion=option_pool_expansion
            )
            
            cap_table_history.append(snapshot)
            current_cap_table = post_money_cap_table
            cumulative_invested += amount
        
        # Add current/final state with option exercise assumption
        final_cap_table = self._apply_option_exercise(current_cap_table)
        
        return {
            "history": cap_table_history,
            "current_cap_table": current_cap_table,
            "final_cap_table_at_exit": final_cap_table,
            "total_raised": cumulative_invested,
            "num_rounds": len(funding_rounds),
            "founder_dilution": 100.0 - current_cap_table.get("Founders", 0),
            "sankey_data": self._format_for_sankey(cap_table_history),
            "waterfall_data": self._format_for_waterfall(cap_table_history)
        }
    
    def _apply_option_exercise(self, cap_table: Dict[str, float]) -> Dict[str, float]:
        """
        Apply 75% unexercised option assumption at exit
        """
        final = cap_table.copy()
        
        if "Option Pool" in final:
            option_pool = final["Option Pool"]
            # Remove full option pool
            del final["Option Pool"]
            # Add back exercised and unexercised portions
            final["Employees (exercised)"] = option_pool * self.option_exercise_rate
            final["Employees (unexercised)"] = option_pool * (1 - self.option_exercise_rate)
            
            # Normalize to 100%
            total = sum(final.values())
            final = {k: (v / total) * 100 for k, v in final.items()}
        
        return final
    
    def _get_typical_dilution(self, round_name: str) -> float:
        """Get typical dilution by round stage"""
        return self.DILUTION_BY_STAGE.get(round_name, 0.15)
    
    def _format_for_sankey(self, history: List[CapTableSnapshot]) -> Dict[str, Any]:
        """
        Format cap table history as Sankey diagram data
        Shows flow of ownership through rounds
        """
        nodes = []
        links = []
        node_id = 0
        node_map = {}
        
        # Create nodes for each stakeholder at each round
        for i, snapshot in enumerate(history):
            round_prefix = f"R{i}_"
            
            # Pre-money nodes
            for stakeholder, ownership in snapshot.pre_money_ownership.items():
                node_name = f"{round_prefix}PRE_{stakeholder}"
                if node_name not in node_map:
                    nodes.append({
                        "id": node_id,
                        "name": stakeholder,
                        "round": snapshot.round_name,
                        "stage": "pre",
                        "ownership": ownership
                    })
                    node_map[node_name] = node_id
                    node_id += 1
            
            # Post-money nodes
            for stakeholder, ownership in snapshot.post_money_ownership.items():
                node_name = f"{round_prefix}POST_{stakeholder}"
                if node_name not in node_map:
                    nodes.append({
                        "id": node_id,
                        "name": stakeholder,
                        "round": snapshot.round_name,
                        "stage": "post",
                        "ownership": ownership
                    })
                    node_map[node_name] = node_id
                    node_id += 1
            
            # Create links showing dilution
            for stakeholder in snapshot.pre_money_ownership:
                if stakeholder in snapshot.post_money_ownership:
                    pre_node = node_map[f"{round_prefix}PRE_{stakeholder}"]
                    post_node = node_map[f"{round_prefix}POST_{stakeholder}"]
                    
                    links.append({
                        "source": pre_node,
                        "target": post_node,
                        "value": snapshot.post_money_ownership[stakeholder],
                        "type": "dilution",
                        "round": snapshot.round_name
                    })
            
            # Links for new investors
            for investor in snapshot.new_investors:
                if investor in snapshot.post_money_ownership or f"{investor} (Lead)" in snapshot.post_money_ownership:
                    investor_key = investor if investor in snapshot.post_money_ownership else f"{investor} (Lead)"
                    post_node = node_map[f"{round_prefix}POST_{investor_key}"]
                    
                    links.append({
                        "source": node_id,  # New money source
                        "target": post_node,
                        "value": snapshot.post_money_ownership[investor_key],
                        "type": "investment",
                        "round": snapshot.round_name,
                        "amount": snapshot.investment_amount
                    })
                    
                    nodes.append({
                        "id": node_id,
                        "name": f"New Investment - {snapshot.round_name}",
                        "type": "funding_source"
                    })
                    node_id += 1
        
        return {
            "nodes": nodes,
            "links": links,
            "metadata": {
                "num_rounds": len(history),
                "total_nodes": len(nodes),
                "total_links": len(links)
            }
        }
    
    def _format_for_waterfall(self, history: List[CapTableSnapshot]) -> List[Dict[str, Any]]:
        """
        Format as waterfall showing founder dilution through rounds
        """
        waterfall_data = []
        
        # Start with 100% founder ownership
        waterfall_data.append({
            "name": "Initial (Founders)",
            "value": 100,
            "category": "initial",
            "cumulative": 100
        })
        
        cumulative = 100
        
        for snapshot in history:
            # Calculate founder dilution this round
            pre_founder = snapshot.pre_money_ownership.get("Founders", 0)
            post_founder = snapshot.post_money_ownership.get("Founders", 0)
            dilution = pre_founder - post_founder
            
            cumulative = post_founder
            
            waterfall_data.append({
                "name": f"{snapshot.round_name} Dilution",
                "value": -dilution,
                "category": "dilution",
                "cumulative": cumulative,
                "details": {
                    "amount_raised": snapshot.investment_amount,
                    "pre_money": snapshot.pre_money_valuation,
                    "post_money": snapshot.post_money_valuation,
                    "new_investors": snapshot.new_investors
                }
            })
            
            # Add option pool expansion if any
            if snapshot.option_pool_expansion > 0:
                option_dilution = snapshot.option_pool_expansion * 100
                cumulative -= option_dilution
                
                waterfall_data.append({
                    "name": f"{snapshot.round_name} Option Pool",
                    "value": -option_dilution,
                    "category": "options",
                    "cumulative": cumulative
                })
        
        # Final founder ownership
        waterfall_data.append({
            "name": "Final Founder Ownership",
            "value": 0,
            "category": "final",
            "cumulative": cumulative,
            "is_total": True
        })
        
        return waterfall_data
    
    def calculate_our_entry_impact(
        self,
        company_data: Dict[str, Any],
        our_investment: float,
        round_name: str = "Series B"
    ) -> Dict[str, Any]:
        """
        Calculate how our investment affects the cap table
        Shows pre and post our entry
        """
        
        # Get current cap table
        current_cap = self.calculate_full_cap_table_history(company_data)
        final_current = current_cap["final_cap_table_at_exit"]
        
        # Calculate our entry
        current_valuation = company_data.get("valuation", 100_000_000)
        post_money = current_valuation + our_investment
        our_ownership = (our_investment / post_money) * 100
        
        # Create new cap table with us
        new_cap_table = {}
        dilution = our_investment / post_money
        
        # Dilute everyone
        for stakeholder, ownership in final_current.items():
            new_cap_table[stakeholder] = ownership * (1 - dilution)
        
        # Add ourselves
        new_cap_table[f"Our Fund ({round_name})"] = our_ownership
        
        return {
            "pre_investment_cap_table": final_current,
            "post_investment_cap_table": new_cap_table,
            "our_ownership": our_ownership,
            "our_investment": our_investment,
            "pre_money_valuation": current_valuation,
            "post_money_valuation": post_money,
            "dilution_to_existing": dilution * 100,
            "founder_ownership_before": final_current.get("Founders", 0),
            "founder_ownership_after": new_cap_table.get("Founders", 0)
        }