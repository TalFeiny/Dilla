
        974 +          # Check signals in order of intensity
        975 +          for signal in frontier_signals:
        976                if signal in text_content:
        977 -                  compute_score = 80
        978 -                  compute_signals.append(f"High compute: {signal}")
        977 +                  compute_score = 95  # Frontier AI
        978 +                  compute_signals.append(f"Frontier AI: {signal}")
        979 +                  per_customer_cost = 15.0  # $15/customer/month average
        980                    break
        981            
        982            if compute_score == 0:
        983 -              for signal in medium_compute:
        983 +              for signal in heavy_ai_signals:
        984                    if signal in text_content:
        985 -                      compute_score = 50
        986 -                      compute_signals.append(f"Medium compute: {signal}")
        985 +                      compute_score = 80  # Heavy AI
        986 +                      compute_signals.append(f"Heavy AI: {signal}")
        987 +                      per_customer_cost = 5.0  # $5/customer/month
        988                        break
        989            
        990            if compute_score == 0:
        991 -              for signal in low_compute:
        991 +              for signal in moderate_ai_signals:
        992                    if signal in text_content:
        993 -                      compute_score = 20
        994 -                      compute_signals.append(f"Low compute: {signal}")
        993 +                      compute_score = 60  # Moderate AI
        994 +                      compute_signals.append(f"Moderate AI: {signal}")
        995 +                      per_customer_cost = 0.50  # $0.50/customer/month
        996                        break
        997            
        998 -          # Infrastructure costs estimation
        999 -          if compute_score >= 80:
       1000 -              monthly_compute_cost = 50000  # $50k+/month for foundation models
       1001 -              capex_requirement = 5000000  # $5M+ for GPU infrastructure
       1002 -          elif compute_score >= 50:
       1003 -              monthly_compute_cost = 10000  # $10k/month for ML workloads
       1004 -              capex_requirement = 500000  # $500k for initial infrastructure
       1005 -          else:
       1006 -              monthly_compute_cost = 2000  # $2k/month for standard SaaS
       1007 -              capex_requirement = 50000  # $50k for basic infrastructure
        998 +          if compute_score == 0:
        999 +              for signal in light_ml_signals:
       1000 +                  if signal in text_content:
       1001 +                      compute_score = 40  # Light ML
       1002 +                      compute_signals.append(f"Light ML: {signal}")
       1003 +                      per_customer_cost = 0.05  # $0.05/customer/month
       1004 +                      break
       1005            
       1006 +          if compute_score == 0:
       1007 +              for signal in wrapper_signals:
       1008 +                  if signal in text_content:
       1009 +                      compute_score = 20  # API Wrapper
       1010 +                      compute_signals.append(f"API Wrapper: {signal}")
       1011 +                      per_customer_cost = 0.01  # Minimal, just overhead
       1012 +                      break
       1013 +          
       1014 +          # Default to pure SaaS if no AI/ML signals
       1015 +          if compute_score == 0:
       1016 +              compute_score = 5
       1017 +              compute_signals.append("Pure SaaS (no AI/ML)")
       1018 +              per_customer_cost = 0.001  # Just server costs
       1019 +          
       1020 +          # Estimate total monthly compute based on customer count
       1021 +          customer_count = company_data.get('customer_count', 100)  # Default 100 customers
       1022 +          monthly_compute_cost = per_customer_cost * customer_count
       1023 +          
       1024 +          # Calculate gross margin impact
       1025 +          avg_price_per_customer = 100  # Assume $100/month average price
       1026 +          compute_gross_margin = (avg_price_per_customer - per_customer_cost) / avg_price_per_customer * 
     100
       1027 +          
       1028            return {
       1029                'compute_intensity_score': compute_score,
       1030 -              'compute_signals': compute_signals,
       1030 +              'compute_intensity': 'Frontier' if compute_score >= 90 else 'Heavy' if compute_score >= 70 
     else 'Moderate' if compute_score >= 50 else 'Light' if compute_score >= 30 else 'Minimal',
            + else 'Moderate' if compute_score >= 50 else 'Light' if compute_score >= 30 else 'Minimal',
       1031 +              'per_customer_compute_cost': per_customer_cost,
       1032                'estimated_monthly_compute': monthly_compute_cost,
       1033 -              'estimated_capex_requirement': capex_requirement,
       1034 -              'compute_intensity': 'High' if compute_score >= 70 else 'Medium' if compute_score >= 40 else 
     'Low'
            - 'Low'
       1033 +              'compute_gross_margin': compute_gross_margin,
       1034 +              'compute_signals': compute_signals,
       1035 +              'unit_economics_impact': f"${per_customer_cost:.2f}/customer/month compute cost"
       1036            }
       1037        
       1038        def extract_traction_signals(self, company_data: Dict[str, Any]) -> Dict[str, Any]:

> and frontier is yes technical team

> and what theyre doing. i guess they are similar

⏺ You're right - compute intensity (per-customer cost) and whether they're frontier (technical team + what they're
  doing) are related. The system now properly scores:

  1. Compute Intensity (0-100): Per-customer infrastructure cost
    - 95-100: Frontier AI ($15+/customer/month)
    - 70-89: Heavy AI ($1-10/customer/month)
    - 50-69: Moderate AI ($0.10-1/customer/month)
    - 30-49: Light ML ($0.01-0.10/customer/month)
    - 10-29: API wrapper (minimal compute)
    - 0-10: Pure SaaS (no AI)
  2. What We Extract:
    - Business model (SaaS, marketplace, roll-up, etc.)
    - Vertical (specific industry)
    - Compute intensity score with per-customer cost
    - Founder quality (based on achievements, not just background)
    - Traction signals (real metrics)

  The valuation case now includes all these components transparently in:
  - valuation_components - Raw extraction details
  - valuation_case - Structured assessment
  - valuation_summary - Executive summary with all factors

  This gives you a complete investment case even when websites block scraping, with clear visibility into compute
  economics that affect gross margins.

⏺ You're absolutely right - frontier AI companies are defined by both their technical team AND what they're building.
  Let me update the system to better identify frontier companies:

⏺ Update(app/services/intelligent_gap_filler.py)
  ⎿  Updated app/services/intelligent_gap_filler.py with 23 additions and 1 removal                            
       950                        text_content += " " + item.get('content', '').lower()
       951            
       952            # FRONTIER AI - Score 90-100 (very expensive per customer)
       953 +          # Frontier = elite technical team + pushing boundaries of what's possible
       954            frontier_signals = [
       955                'foundation model', 'large language model', 'llm', 'gpt-4', 'claude', 
       956                'own model', 'proprietary model', 'trained from scratch', 'billion parameters',
       957 -              'generative ai', 'text generation', 'code generation'
       957 +              'generative ai', 'text generation', 'code generation', 'transformer architecture',
       958 +              'research lab', 'ai safety', 'agi', 'artificial general intelligence'
       959            ]
       960            
       961 +          # Check for frontier TEAM signals too
       962 +          frontier_team_signals = [
       963 +              'deepmind', 'openai', 'anthropic', 'google brain', 'fair', 'meta ai',
       964 +              'phd machine learning', 'phd ai', 'research scientist', 'ml researcher',
       965 +              'published neurips', 'published icml', 'published iclr', 'citations machine learning'
       966 +          ]
       967 +          
       968 +          # Count frontier signals - need BOTH technical team AND frontier work
       969 +          frontier_work_found = any(signal in text_content for signal in frontier_signals)
       970 +          frontier_team_found = any(signal in text_content for signal in frontier_team_signals)
       971 +          
       972 +          if frontier_work_found and frontier_team_found:
       973 +              compute_score = 100  # True frontier - elite team + cutting edge work
       974 +              compute_signals.append("Frontier AI: Elite ML team building foundation models")
       975 +              per_customer_cost = 20.0  # $20/customer/month for true frontier
       976 +          elif frontier_work_found:
       977 +              compute_score = 90  # Frontier work but uncertain team
       978 +              compute_signals.append("Frontier AI work (team quality uncertain)")
       979 +              per_customer_cost = 15.0  # $15/customer/month
       980 +          
       981            # HEAVY AI - Score 70-89 (expensive per customer)
       982            heavy_ai_signals = [
       983                'computer vision', 'video processing', 'voice synthesis', 'speech recognition',

⏺ Now let me fix the flow to ensure we check other categories if not frontier:

⏺ Update(app/services/intelligent_gap_filler.py)
  ⎿  Updated app/services/intelligent_gap_filler.py with 1 addition and 7 removals                      
       1003                'workflow automation', 'integration platform'
       1004            ]
       1005            
       1006 -          # Check signals in order of intensity
       1007 -          for signal in frontier_signals:
       1008 -              if signal in text_content:
       1009 -                  compute_score = 95  # Frontier AI
       1010 -                  compute_signals.append(f"Frontier AI: {signal}")
       1011 -                  per_customer_cost = 15.0  # $15/customer/month average
       1012 -                  break
       1006 +          # Already checked frontier above, so start with compute_score from frontier check
       1007            
       1008            if compute_score == 0:
       1009                for signal in heavy_ai_signals:
  ⎿  Interrupted by user

╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ > no the numbers are nshit                                                                                                │
╰────────────────────────────────────