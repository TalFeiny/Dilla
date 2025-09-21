"""
Pre and Post Money Cap Table Calculator
Shows ownership before and after each funding round
"""

from typing import Dict, List, Any, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, getcontext
import decimal
import logging

logger = logging.getLogger(__name__)
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
    pro_rata_investments: Dict[str, Decimal] = None  # Pro-rata amounts by investor
    dilution_without_pro_rata: Dict[str, Decimal] = None  # What ownership would be without pro-rata
    
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
    OPTION_EXERCISE_RATE = Decimal('0.30')  # 70% unexercised (30% exercised - industry benchmark)
    
    def __init__(self):
        self.option_exercise_rate = self.OPTION_EXERCISE_RATE
        self.pro_rata_threshold = Decimal('0.05')  # 5% ownership typically gets pro-rata rights
    
    def calculate_pro_rata_investment(
        self,
        current_ownership: Decimal,
        new_money_raised: Decimal,
        pre_money_valuation: Decimal
    ) -> Dict[str, Any]:
        """
        Calculate how much an investor needs to invest to maintain ownership
        
        Returns:
            - pro_rata_amount: Investment needed to maintain ownership
            - new_ownership_with_pro_rata: Ownership if they invest pro-rata
            - new_ownership_without_pro_rata: Ownership if they don't participate
        """
        post_money = pre_money_valuation + new_money_raised
        
        # To maintain ownership %, need to own same % of post-money
        # current_ownership % of post_money = their_value
        # their_value = pre_money_ownership + new_investment
        # new_investment = (current_ownership * post_money) - (current_ownership * pre_money)
        pro_rata_amount = current_ownership * new_money_raised
        
        # Ownership WITH pro-rata investment
        ownership_with_pro_rata = current_ownership  # Maintains exact ownership
        
        # Ownership WITHOUT pro-rata (diluted)
        ownership_without_pro_rata = (current_ownership * pre_money_valuation) / post_money
        
        # Dilution amount
        dilution = current_ownership - ownership_without_pro_rata
        
        return {
            "pro_rata_investment_needed": float(pro_rata_amount),
            "ownership_with_pro_rata": float(ownership_with_pro_rata * 100),
            "ownership_without_pro_rata": float(ownership_without_pro_rata * 100),
            "dilution_if_no_pro_rata": float(dilution * 100),
            "has_pro_rata_rights": current_ownership >= self.pro_rata_threshold
        }
        
    def calculate_fund_performance_impact(
        self,
        initial_investment: float,
        current_ownership: float,
        exit_value: float,
        years_held: float,
        pro_rata_invested: float = 0
    ) -> Dict[str, float]:
        """
        Calculate how this investment impacts fund performance metrics
        
        Args:
            initial_investment: Original investment amount
            current_ownership: Current ownership % (0-100)
            exit_value: Total exit valuation
            years_held: Years from investment to exit
            pro_rata_invested: Additional capital deployed via pro-rata
        
        Returns:
            Dict with DPI, TVPI, IRR, and other fund metrics
        """
        total_invested = initial_investment + pro_rata_invested
        proceeds = (current_ownership / 100) * exit_value
        
        # DPI (Distributed to Paid-In) - actual cash returned
        dpi = proceeds / total_invested if total_invested > 0 else 0
        
        # TVPI (Total Value to Paid-In) - for liquid exit, same as DPI
        tvpi = dpi
        
        # IRR calculation
        if years_held > 0 and total_invested > 0:
            irr = ((proceeds / total_invested) ** (1 / years_held)) - 1
        else:
            irr = 0
            
        # Multiple on Invested Capital (MOIC)
        moic = proceeds / total_invested if total_invested > 0 else 0
        
        # Capital efficiency metrics
        capital_efficiency = proceeds / initial_investment if initial_investment > 0 else 0
        pro_rata_impact = (pro_rata_invested / total_invested * 100) if total_invested > 0 else 0
        
        return {
            "dpi": dpi,
            "tvpi": tvpi,
            "irr": irr * 100,  # Convert to percentage
            "moic": moic,
            "total_invested": total_invested,
            "proceeds": proceeds,
            "capital_efficiency": capital_efficiency,
            "pro_rata_deployed_pct": pro_rata_impact,
            "net_profit": proceeds - total_invested,
            "years_held": years_held
        }
    
    def calculate_full_cap_table_history(
        self, 
        company_data: Union[Dict[str, Any], List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Calculate complete cap table evolution through all rounds
        Returns data structured for Sankey/waterfall visualization
        Handles SAFE/convertible note conversions at priced rounds
        """
        
        # Handle both dict with funding_rounds key and direct list of rounds
        if isinstance(company_data, list):
            funding_rounds = company_data
            is_yc = False  # Default if just rounds list
            geography = "Unknown"
        else:
            funding_rounds = company_data.get("funding_rounds", [])
            is_yc = company_data.get("is_yc", False)
            geography = company_data.get("geography", "Unknown")
        
        # Handle empty or invalid funding rounds gracefully
        if not funding_rounds:
            # Check if it's a YC company without funding rounds yet
            # Extract founder names for empty rounds case
            founder_names = []
            if isinstance(company_data, dict):
                if 'founders' in company_data and company_data['founders']:
                    founder_names = company_data['founders']
                elif 'founder' in company_data:
                    if isinstance(company_data['founder'], list):
                        founder_names = company_data['founder']
                    else:
                        founder_names = [company_data['founder']]
            
            if founder_names:
                initial_cap_table = {}
                ownership_per = 100.0 / len(founder_names)
                for f in founder_names:
                    name = f.get('name', f) if isinstance(f, dict) else str(f)
                    label = " (Co-Founder)" if len(founder_names) > 1 else " (Founder)"
                    initial_cap_table[f"{name}{label}"] = ownership_per
            else:
                initial_cap_table = {"Founders": 100.0}
            
            if is_yc:
                initial_cap_table["YC SAFE (pending)"] = 0.0  # Will convert at Series A
            
            return {
                "history": [],
                "current_cap_table": initial_cap_table,
                "final_cap_table_at_exit": initial_cap_table,
                "total_raised": 0,
                "num_rounds": 0,
                "founder_dilution": 0,
                "sankey_data": {"nodes": [], "links": []},
                "waterfall_data": [],
                "has_pending_safes": is_yc
            }
        
        # Initialize with founders owning 100%
        cap_table_history = []
        
        # Extract founder information if available
        founders = []
        if isinstance(company_data, dict):
            # Check for founders in company_data
            if 'founders' in company_data and company_data['founders']:
                founders = company_data['founders']
            elif 'founder' in company_data and company_data['founder']:
                # Single founder field
                if isinstance(company_data['founder'], list):
                    founders = [{'name': f} if isinstance(f, str) else f for f in company_data['founder']]
                else:
                    founders = [{'name': company_data['founder']}]
        
        # Initialize cap table with actual founder names if available
        if founders and len(founders) > 0:
            current_cap_table = {}
            # Split ownership equally among founders
            ownership_per_founder = Decimal('100.0') / Decimal(len(founders))
            for founder in founders:
                if isinstance(founder, dict):
                    name = founder.get('name', 'Unknown Founder')
                else:
                    name = str(founder)
                # Add (Co-Founder) label if multiple founders
                label = " (Co-Founder)" if len(founders) > 1 else " (Founder)"
                current_cap_table[f"{name}{label}"] = ownership_per_founder
        else:
            # Fallback to generic "Founders"
            current_cap_table = {
                "Founders": Decimal('100.0')
            }
        
        # Track cumulative dilution and pending SAFEs
        cumulative_invested = Decimal('0')
        pending_safes = []
        
        # If YC company, add YC SAFE to pending
        if is_yc:
            yc_safe_amount = Decimal('500000')  # Standard YC $500k
            pending_safes.append({
                "investor": "Y Combinator",
                "amount": yc_safe_amount,
                "discount": Decimal('0.20'),  # 20% discount typical for YC
                "cap": None,  # YC typically uncapped
                "type": "SAFE"
            })
        
        for i, round_data in enumerate(funding_rounds):
            # Skip invalid rounds
            if not isinstance(round_data, dict):
                continue
                
            round_name = round_data.get("round", f"Round {i+1}")
            
            # Safely convert amount to Decimal
            try:
                amount = Decimal(str(round_data.get("amount", 0)))
                if amount <= 0:
                    continue  # Skip rounds with no or negative amount
            except (decimal.InvalidOperation, ValueError, TypeError):
                continue
            
            # Safely convert pre_money to Decimal
            try:
                pre_money = Decimal(str(round_data.get("pre_money_valuation", 0)))
            except (decimal.InvalidOperation, ValueError, TypeError):
                pre_money = Decimal('0')
            
            # If no pre-money, estimate from amount and typical dilution
            if pre_money == 0:
                try:
                    dilution_value = self._get_typical_dilution(round_name)
                    logger.info(f"Round {round_name}: _get_typical_dilution returned {dilution_value} (type: {type(dilution_value)})")
                    typical_dilution = Decimal(str(dilution_value))
                    logger.info(f"Round {round_name}: No pre_money provided, using typical dilution {typical_dilution:.2%}")
                    logger.info(f"Round {round_name}: Amount value = {amount}, type = {type(amount)}")
                    
                    if typical_dilution > 0 and amount > 0:
                        # Calculate pre-money: If raising X at Y% dilution, pre = X/Y - X
                        # Ensure we're working with proper Decimal values
                        division_result = amount / typical_dilution
                        logger.info(f"Round {round_name}: Division result = {division_result}")
                        pre_money = division_result.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) - amount
                        logger.info(f"Calculated pre_money = ${pre_money:,.0f} from amount=${amount:,.0f} at {typical_dilution:.2%} dilution")
                    else:
                        # Default fallback if dilution is 0
                        pre_money = amount * Decimal('4')  # Assume 20% dilution (amount / 0.2 - amount)
                        logger.warning(f"Using fallback pre_money calculation: ${pre_money:,.0f}")
                except (decimal.InvalidOperation, ZeroDivisionError, TypeError, ValueError) as e:
                    # Fallback to standard valuation multiple
                    logger.error(f"Error calculating pre_money: {type(e).__name__}: {e}, using fallback")
                    pre_money = amount * Decimal('4')  # Assume 20% dilution
            
            # SAFE CONVERSION: Check if this is a priced round (Series A or later)
            # and convert any pending SAFEs
            is_priced_round = any(stage in round_name for stage in ["Series", "Round B", "Round C"])
            safe_conversion_shares = Decimal('0')
            converted_safes = []
            
            if is_priced_round and pending_safes:
                logger.info(f"Converting {len(pending_safes)} pending SAFEs at {round_name}")
                
                for safe in pending_safes:
                    safe_amount = safe["amount"]
                    safe_discount = safe.get("discount", Decimal('0'))
                    safe_cap = safe.get("cap")
                    
                    # Calculate conversion price
                    if safe_cap and pre_money > safe_cap:
                        # Cap is triggered, use cap valuation
                        conversion_price = safe_cap
                    else:
                        # Use pre-money with discount
                        conversion_price = pre_money * (Decimal('1') - safe_discount)
                    
                    # Calculate ownership from SAFE conversion
                    safe_ownership_decimal = safe_amount / (conversion_price + safe_amount)
                    safe_conversion_shares += safe_ownership_decimal
                    
                    converted_safes.append({
                        "investor": safe["investor"],
                        "amount": float(safe_amount),
                        "conversion_price": float(conversion_price),
                        "ownership_acquired": float(safe_ownership_decimal * 100)
                    })
                    
                    logger.info(f"  - {safe['investor']}: ${safe_amount:,} converts to {safe_ownership_decimal*100:.2f}% ownership")
                
                # Clear pending SAFEs after conversion
                pending_safes = []
            
            # Adjust post_money to include SAFE conversions
            post_money = pre_money + amount
            
            # Save pre-money state
            pre_money_cap_table = current_cap_table.copy()
            
            # Calculate dilution INCLUDING SAFE conversions
            total_new_ownership = safe_conversion_shares + (amount / post_money)
            dilution = total_new_ownership.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            
            # Create post-money cap table efficiently
            post_money_cap_table = {}
            
            # Apply dilution to all existing shareholders at once
            dilution_factor = Decimal('1') - dilution
            for shareholder, ownership in current_cap_table.items():
                # FIXED: Ensure ownership is a Decimal, not a dict
                if isinstance(ownership, dict):
                    logger.error(f"ERROR: current_cap_table[{shareholder}] is a dict: {ownership}")
                    # Try to extract a value from the dict if possible
                    if 'value' in ownership:
                        ownership = Decimal(str(ownership['value']))
                    elif 'amount' in ownership:
                        ownership = Decimal(str(ownership['amount']))
                    else:
                        logger.error(f"Cannot extract value from dict for {shareholder}, skipping")
                        continue
                elif not isinstance(ownership, Decimal):
                    ownership = Decimal(str(ownership))
                post_money_cap_table[shareholder] = (ownership * dilution_factor).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            
            # Add converted SAFE holders to cap table
            if converted_safes:
                for safe_conversion in converted_safes:
                    investor_name = safe_conversion["investor"]
                    ownership_pct = Decimal(str(safe_conversion["ownership_acquired"]))
                    post_money_cap_table[f"{investor_name} (SAFE)"] = ownership_pct
                    logger.info(f"Added {investor_name} (SAFE) with {ownership_pct:.2f}% ownership")
            
            # Add new investors (only get the new round amount, not SAFE conversions)
            investors = round_data.get("investors", [])
            lead_investor = round_data.get("lead_investor")
            # Round ownership is ONLY the new money, not SAFEs
            round_ownership = (amount / post_money) * Decimal('100')
            
            logger.info(f"Round {round_name}: new_money_dilution={amount/post_money:.2%}, safe_dilution={safe_conversion_shares:.2%}, total_dilution={dilution:.2%}")
            
            if lead_investor:
                # Lead takes 60% of round
                post_money_cap_table[f"{lead_investor} (Lead)"] = (round_ownership * self.LEAD_INVESTOR_SHARE).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
                # Others split remaining 40%
                other_investors = [i for i in investors if i != lead_investor]
                if other_investors:
                    other_stake = round_ownership * (Decimal('1') - self.LEAD_INVESTOR_SHARE)
                    per_investor = other_stake / Decimal(len(other_investors))
                    for investor in other_investors:
                        post_money_cap_table[investor] = per_investor
            elif investors:
                # Equal split among all investors
                per_investor = round_ownership / Decimal(len(investors))
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
                    # FIXED: Check if value is a dict before multiplying
                    current_val = post_money_cap_table[shareholder]
                    if isinstance(current_val, dict):
                        logger.error(f"ERROR: post_money_cap_table[{shareholder}] is a dict: {current_val}")
                        continue
                    post_money_cap_table[shareholder] = current_val * (Decimal('1') - Decimal(str(option_pool_expansion)))
                # FIXED: Don't multiply by 100 - option_pool_expansion is already in decimal form (0.15 = 15%)
                # Convert to percentage same as other shareholders
                post_money_cap_table["Option Pool"] = Decimal(str(option_pool_expansion)) * Decimal('100')
            
            # Calculate pro-rata for existing investors
            pro_rata_investments = {}
            dilution_without_pro_rata = {}
            
            # FIXED: Skip pro-rata for the first round (when only Founders exist)
            # Founders don't have pro-rata rights because they didn't invest cash
            founders_only = all("Founder" in k or k == "Founders" for k in pre_money_cap_table.keys())
            is_first_round = len(cap_table_history) == 0 or founders_only
            
            if not is_first_round:
                # Track total pro-rata participation
                total_pro_rata_amount = Decimal('0')
                pro_rata_participants = {}
                
                # First pass: identify who exercises pro-rata
                for investor, ownership in pre_money_cap_table.items():
                    # Skip Founders - they don't have pro-rata rights
                    if "Founder" in investor or investor == "Founders":
                        continue
                    if ownership >= self.pro_rata_threshold * 100:  # Convert to percentage
                        # This investor has pro-rata rights
                        pro_rata_calc = self.calculate_pro_rata_investment(
                            ownership / 100,  # Convert back to decimal
                            amount,
                            pre_money
                        )
                        
                        if pro_rata_calc["has_pro_rata_rights"]:
                            pro_rata_investments[investor] = pro_rata_calc["pro_rata_investment_needed"]
                            dilution_without_pro_rata[investor] = pro_rata_calc["ownership_without_pro_rata"]
                            
                            # For now, assume major investors (>10%) exercise, others don't
                            if ownership >= 10:
                                pro_rata_participants[investor] = ownership / 100  # Store as decimal
                                total_pro_rata_amount += Decimal(str(pro_rata_calc["pro_rata_investment_needed"]))
                
                # Second pass: adjust ALL ownership percentages based on pro-rata participation
                if pro_rata_participants:
                    # Calculate the new round's available ownership after pro-rata
                    total_new_round_ownership = dilution * Decimal('100')  # Convert to percentage
                    
                    # Pro-rata participants maintain their ownership
                    for investor, pre_ownership_decimal in pro_rata_participants.items():
                        post_money_cap_table[investor] = pre_ownership_decimal * Decimal('100')  # Convert back to percentage
                    
                    # The remaining new money (after pro-rata) gets allocated to new investors
                    remaining_new_money = amount - total_pro_rata_amount
                    remaining_ownership = (remaining_new_money / post_money) * Decimal('100')
                    
                    # Now ALL non-participating shareholders get diluted proportionally
                    # This includes both non-participating existing investors AND reduces the new investor allocation
                    
                    # Calculate total dilution factor for non-participants
                    pro_rata_ownership_taken = sum(Decimal(str(v)) for v in pro_rata_participants.values()) * Decimal('100')
                    ownership_available_for_others = Decimal('100') - pro_rata_ownership_taken
                    dilution_factor = ownership_available_for_others / (Decimal('100') - (total_pro_rata_amount / post_money) * Decimal('100'))
                    
                    # Apply dilution to all non-participating existing shareholders
                    for shareholder, current_ownership in list(post_money_cap_table.items()):
                        if shareholder not in pro_rata_participants and shareholder not in investors and f"{shareholder} (Lead)" not in post_money_cap_table:
                            # This shareholder gets diluted
                            if isinstance(current_ownership, dict):
                                logger.error(f"ERROR: post_money_cap_table[{shareholder}] is a dict: {current_ownership}")
                                continue
                            post_money_cap_table[shareholder] = current_ownership * dilution_factor
                    
                    # Allocate remaining ownership to new investors
                    if lead_investor:
                        # Lead takes 60% of remaining allocation
                        post_money_cap_table[f"{lead_investor} (Lead)"] = remaining_ownership * self.LEAD_INVESTOR_SHARE
                        # Others split remaining 40%
                        other_investors = [i for i in investors if i != lead_investor]
                        if other_investors:
                            other_stake = remaining_ownership * (Decimal('1') - self.LEAD_INVESTOR_SHARE)
                            per_investor = other_stake / Decimal(len(other_investors))
                            for investor in other_investors:
                                post_money_cap_table[investor] = per_investor
                    elif investors:
                        # Equal split among all new investors
                        per_investor = remaining_ownership / Decimal(len(investors))
                        for investor in investors:
                            post_money_cap_table[investor] = per_investor
                    else:
                        # Generic investor label
                        post_money_cap_table[f"{round_name} Investors"] = remaining_ownership
            
            # Create snapshot as dict (not dataclass) for JSON serialization
            snapshot = {
                "round_name": round_name,
                "date": round_data.get("date", datetime.now()),
                "pre_money_valuation": float(pre_money),
                "investment_amount": float(amount),
                "post_money_valuation": float(post_money),
                "pre_money_ownership": {k: float(v) for k, v in pre_money_cap_table.items()},
                "post_money_ownership": {k: float(v) for k, v in post_money_cap_table.items()},
                "converted_safes": converted_safes if converted_safes else [],
                "new_investors": investors,
                "option_pool_expansion": float(option_pool_expansion),
                "pro_rata_investments": pro_rata_investments,
                "dilution_without_pro_rata": dilution_without_pro_rata
            }
            
            cap_table_history.append(snapshot)
            # FIXED: Ensure all values in post_money_cap_table are Decimals before assigning
            cleaned_cap_table = {}
            for k, v in post_money_cap_table.items():
                if isinstance(v, dict):
                    logger.error(f"ERROR: post_money_cap_table[{k}] is still a dict after processing: {v}")
                    if 'value' in v:
                        cleaned_cap_table[k] = Decimal(str(v['value']))
                    else:
                        cleaned_cap_table[k] = Decimal('0')
                elif isinstance(v, Decimal):
                    cleaned_cap_table[k] = v
                else:
                    cleaned_cap_table[k] = Decimal(str(v))
            current_cap_table = cleaned_cap_table
            cumulative_invested += amount
        
        # Add current/final state with option exercise assumption
        final_cap_table = self._apply_option_exercise(current_cap_table)
        
        # Convert Decimal values to float for JSON serialization
        current_cap_table_float = {k: float(v) for k, v in current_cap_table.items()}
        final_cap_table_float = {k: float(v) for k, v in final_cap_table.items()} if isinstance(final_cap_table, dict) else final_cap_table
        
        # Calculate total pro-rata capital deployed
        total_pro_rata = sum(
            sum(snapshot.get("pro_rata_investments", {}).values()) if snapshot.get("pro_rata_investments") else 0
            for snapshot in cap_table_history
        )
        
        # Calculate fund performance impact for a hypothetical fund
        # Assume fund invested in Series A at 10% ownership
        fund_metrics = {}
        for i, snapshot in enumerate(cap_table_history):
            if "Series A" in snapshot["round_name"]:
                initial_investment = snapshot["investment_amount"] * 0.3  # Assume fund took 30% of round
                fund_ownership = snapshot["post_money_ownership"].get("Series A Investors", 10)
                
                # Calculate with pro-rata through subsequent rounds
                pro_rata_total = sum(
                    s.get("pro_rata_investments", {}).get("Series A Investors", 0)
                    for s in cap_table_history[i+1:]
                )
                
                # Assume 5x exit at current valuation
                exit_value = float(cumulative_invested) * 5
                years_held = max(1, len(cap_table_history) - i) * 1.5  # Assume 1.5 years between rounds
                
                fund_metrics = self.calculate_fund_performance_impact(
                    initial_investment,
                    fund_ownership,
                    exit_value,
                    years_held,
                    pro_rata_total
                )
                break
        
        return {
            "history": cap_table_history,
            "current_cap_table": current_cap_table_float,
            "final_cap_table_at_exit": final_cap_table_float,
            "total_raised": float(cumulative_invested),
            "num_rounds": len(cap_table_history),  # Use actual processed rounds count
            "founder_ownership": float(sum(
                v for k, v in current_cap_table.items() 
                if "Founder" in k or k == "Founders"
            )),
            "total_pro_rata_deployed": total_pro_rata,
            "fund_performance_metrics": fund_metrics,
            "sankey_data": self._format_for_sankey(cap_table_history),
            "waterfall_data": self._format_for_waterfall(cap_table_history)
        }
    
    def _apply_option_exercise(self, cap_table: Dict[str, Decimal]) -> Dict[str, float]:
        """
        Apply 70% unexercised option assumption at exit (30% exercised)
        """
        final = cap_table.copy()
        
        if "Option Pool" in final:
            option_pool = final["Option Pool"]
            # Remove full option pool
            del final["Option Pool"]
            # Add back exercised and unexercised portions
            final["Employees (exercised)"] = option_pool * self.option_exercise_rate
            final["Employees (unexercised)"] = option_pool * (Decimal('1') - self.option_exercise_rate)
            
            # Normalize to 100%
            total = sum(final.values())
            if total > 0:
                final = {k: float((v / total) * 100) for k, v in final.items()}
            else:
                final = {k: float(v) for k, v in final.items()}
        else:
            # Just convert to float
            final = {k: float(v) for k, v in final.items()}
        
        return final
    
    def _get_typical_dilution(self, round_name: str) -> float:
        """Get typical dilution by round stage"""
        # First try exact match
        if round_name in self.DILUTION_BY_STAGE:
            return float(self.DILUTION_BY_STAGE[round_name])
        
        # Try case-insensitive match
        round_lower = round_name.lower()
        for stage, dilution in self.DILUTION_BY_STAGE.items():
            if stage.lower() == round_lower:
                return float(dilution)
        
        # Try partial match for Series rounds
        if 'series' in round_lower:
            for stage, dilution in self.DILUTION_BY_STAGE.items():
                if stage.lower() in round_lower or round_lower in stage.lower():
                    return float(dilution)
        
        # Default to 15% for seed-like rounds, 20% for series
        if 'seed' in round_lower:
            return 0.15
        elif 'series' in round_lower:
            return 0.20
        else:
            return 0.15
    
    def _format_for_sankey(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
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
            for stakeholder, ownership in snapshot["pre_money_ownership"].items():
                node_name = f"{round_prefix}PRE_{stakeholder}"
                if node_name not in node_map:
                    nodes.append({
                        "id": node_id,
                        "name": stakeholder,
                        "round": snapshot["round_name"],
                        "stage": "pre",
                        "ownership": ownership
                    })
                    node_map[node_name] = node_id
                    node_id += 1
            
            # Post-money nodes
            for stakeholder, ownership in snapshot["post_money_ownership"].items():
                node_name = f"{round_prefix}POST_{stakeholder}"
                if node_name not in node_map:
                    nodes.append({
                        "id": node_id,
                        "name": stakeholder,
                        "round": snapshot["round_name"],
                        "stage": "post",
                        "ownership": ownership
                    })
                    node_map[node_name] = node_id
                    node_id += 1
            
            # Create links showing dilution
            for stakeholder in snapshot["pre_money_ownership"]:
                if stakeholder in snapshot["post_money_ownership"]:
                    pre_node = node_map[f"{round_prefix}PRE_{stakeholder}"]
                    post_node = node_map[f"{round_prefix}POST_{stakeholder}"]
                    
                    links.append({
                        "source": pre_node,
                        "target": post_node,
                        "value": snapshot["post_money_ownership"][stakeholder],
                        "type": "dilution",
                        "round": snapshot["round_name"]
                    })
            
            # Links for new investors
            for investor in snapshot["new_investors"]:
                if investor in snapshot["post_money_ownership"] or f"{investor} (Lead)" in snapshot["post_money_ownership"]:
                    investor_key = investor if investor in snapshot["post_money_ownership"] else f"{investor} (Lead)"
                    post_node = node_map[f"{round_prefix}POST_{investor_key}"]
                    
                    links.append({
                        "source": node_id,  # New money source
                        "target": post_node,
                        "value": snapshot["post_money_ownership"][investor_key],
                        "type": "investment",
                        "round": snapshot["round_name"],
                        "amount": snapshot["investment_amount"]
                    })
                    
                    nodes.append({
                        "id": node_id,
                        "name": f"New Investment - {snapshot['round_name']}",
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
    
    def _format_for_waterfall(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
            pre_founder = snapshot["pre_money_ownership"].get("Founders", 0)
            post_founder = snapshot["post_money_ownership"].get("Founders", 0)
            dilution = pre_founder - post_founder
            
            cumulative = post_founder
            
            waterfall_data.append({
                "name": f"{snapshot['round_name']} Dilution",
                "value": -dilution,
                "category": "dilution",
                "cumulative": cumulative,
                "details": {
                    "amount_raised": snapshot["investment_amount"],
                    "pre_money": snapshot["pre_money_valuation"],
                    "post_money": snapshot["post_money_valuation"],
                    "new_investors": snapshot["new_investors"]
                }
            })
            
            # Add option pool expansion if any
            if snapshot["option_pool_expansion"] > 0:
                option_dilution = snapshot["option_pool_expansion"] * 100
                cumulative -= option_dilution
                
                waterfall_data.append({
                    "name": f"{snapshot['round_name']} Option Pool",
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
            new_cap_table[stakeholder] = ownership * (Decimal('1') - Decimal(str(dilution)))
        
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