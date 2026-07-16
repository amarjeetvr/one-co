import os
import pandas as pd
import numpy as np

def format_indian_number(num):
    if num is None or pd.isna(num) or num == "" or num == 0 or num == 0.0:
        return ""
    try:
        val = int(float(num))
    except (ValueError, TypeError):
        return ""
    if val == 0:
        return ""
    
    s = str(val)
    if len(s) <= 3:
        return s
    
    last_three = s[-3:]
    remaining = s[:-3]
    
    groups = []
    while remaining:
        groups.append(remaining[-2:])
        remaining = remaining[:-2]
    
    groups.reverse()
    return ",".join(groups) + "," + last_three

def main():
    excel_path = r"e:\amar\development\one-co\urls\consolidated_colleges.xlsx"
    csv_path = r"e:\amar\development\one-co\urls\college_urls.csv"
    
    print(f"Reading {excel_path}...")
    df = pd.read_excel(excel_path)
    print(f"Read {len(df)} rows.")
    
    # Process columns
    rows = []
    for idx, row in df.iterrows():
        url_val = str(row.get('url', '')).strip()
        if not url_val or url_val.lower() == 'nan':
            continue
        
        # Build full URL
        if url_val.startswith('http://') or url_val.startswith('https://'):
            full_url = url_val
        elif url_val.startswith('/'):
            full_url = f"https://collegedunia.com{url_val}"
        else:
            full_url = f"https://collegedunia.com/{url_val}"
            
        avg_pkg = format_indian_number(row.get('avg_salary'))
        high_pkg = format_indian_number(row.get('highest_salary'))
        placement_pct = "" # Not present in Excel
        
        rank_val = row.get('top_ranking_rank')
        if rank_val is not None and not pd.isna(rank_val):
            try:
                rank_int = int(float(rank_val))
                if rank_int > 0:
                    rank_str = f"#{rank_int}"
                else:
                    rank_str = ""
            except (ValueError, TypeError):
                rank_str = ""
        else:
            rank_str = ""
            
        rows.append({
            'url': full_url,
            'listing_avg_package': avg_pkg,
            'listing_highest_package': high_pkg,
            'listing_placement_percentage': placement_pct,
            'listing_rank': rank_str
        })
        
    out_df = pd.DataFrame(rows)
    # Ensure correct column order
    out_df = out_df[['url', 'listing_avg_package', 'listing_highest_package', 'listing_placement_percentage', 'listing_rank']]
    
    print(f"Writing {len(out_df)} rows to {csv_path}...")
    out_df.to_csv(csv_path, index=False, encoding='utf-8')
    print("Done!")

if __name__ == "__main__":
    main()
