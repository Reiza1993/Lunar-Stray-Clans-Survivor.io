#!/usr/bin/env python3
"""
Lunar Clan Intelligence System - Enhanced with Historical Tracking
Complete clan data scraper for https://garrytools.com/lunar

Features:
✅ Handles 13+ clan IDs with smart batching (reuses first 3 for 13th batch)
✅ Extracts complete clan data (rank, stats, member count)
✅ Extracts both Relic Cores AND Attack data for all members
✅ Exports to professional Excel with multiple sheets
✅ HISTORICAL TRACKING - Compares with previous runs
✅ CHANGE DETECTION - Shows member count, rank, and stat changes
✅ Robust error handling and progress tracking
✅ Automatic URL switching between core/attack data
✅ Smart member matching by name (handles different rankings)

Usage:
1. Create clan_ids.txt with your 13 clan IDs (one per line)
2. Run: python3 lunar_final_scraper.py
3. Results saved to lunar_intelligence_TIMESTAMP.xlsx
4. Historical data stored in lunar_data/ folder
"""

import time
import sys
import os
import csv
import json
import shutil
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

class LunarIntelligenceSystem:
    """Production-ready clan intelligence scraper"""
    
    def __init__(self):
        self.driver = None
        self.wait = None
        self.base_url = "https://garrytools.com/lunar"
        self.all_clan_data = []
        self.all_member_data = []
        self.batch_count = 0
        self.processed_clan_ids = set()  # Track already processed clan IDs
        self.clan_configs = {}  # Store LME and phase score data
        
        # Historical tracking
        self.data_dir = "lunar_data"
        self.history_dir = os.path.join(self.data_dir, "history")
        self.current_dir = os.path.join(self.data_dir, "current")
        self.backup_dir = os.path.join(self.data_dir, "backups")
        self.previous_data = None
        self.changes_detected = {}
        
        # Create directories
        self.setup_directories()
        
    def setup_directories(self):
        """Create directory structure for historical data"""
        for directory in [self.data_dir, self.history_dir, self.current_dir, self.backup_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"📁 Created directory: {directory}")
    
    def load_previous_data(self):
        """Load the most recent historical data for comparison"""
        print("📊 Loading previous data for comparison...")
        
        try:
            # Look for the most recent clans data file
            history_files = [f for f in os.listdir(self.history_dir) 
                           if f.startswith("clans_") and f.endswith(".json")]
            
            if not history_files:
                print("📅 No previous data found - this is the first run")
                return None
            
            # Get the most recent file
            latest_file = sorted(history_files)[-1]
            file_path = os.path.join(self.history_dir, latest_file)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                previous_data = json.load(f)
            
            # Extract timestamp from filename: clans_2025-12-15_10-30-00.json
            timestamp = latest_file.replace('clans_', '').replace('.json', '')
            print(f"📈 Previous data loaded from: {timestamp}")
            
            return previous_data
            
        except Exception as e:
            print(f"⚠️ Error loading previous data: {e}")
            return None
    
    def calculate_changes(self, current_data):
        """Calculate changes between current and previous data"""
        if not self.previous_data:
            print("📅 No previous data to compare - skipping change calculation")
            return {}
        
        print("🔍 Calculating changes from previous run...")
        changes = {}
        
        try:
            # Create lookup dictionary for previous data BY GUILD_ID
            previous_clans = {clan['Guild_ID']: clan for clan in self.previous_data.get('clans', [])}
            
            for current_clan in current_data:
                guild_id = current_clan['Guild_ID']
                clan_name = current_clan['Name']  # Keep for display purposes
                
                if guild_id in previous_clans:
                    previous_clan = previous_clans[guild_id]
                    clan_changes = {}
                    
                    # Member count changes
                    current_members = self.parse_member_count(current_clan.get('Member_Count', '0/40'))
                    previous_members = self.parse_member_count(previous_clan.get('Member_Count', '0/40'))
                    if current_members != previous_members:
                        clan_changes['members'] = current_members - previous_members
                    
                    # Global rank changes (lower is better)
                    current_rank = int(current_clan.get('Global_Rank', 999999))
                    previous_rank = int(previous_clan.get('Global_Rank', 999999))
                    if current_rank != previous_rank:
                        clan_changes['rank'] = previous_rank - current_rank  # Positive = improvement
                    
                    # Attack changes
                    current_attack = self.parse_attack_value(current_clan.get('Total_Attack', '0M'))
                    previous_attack = self.parse_attack_value(previous_clan.get('Total_Attack', '0M'))
                    if abs(current_attack - previous_attack) > 0.1:  # Significant change
                        clan_changes['attack'] = current_attack - previous_attack
                    
                    # Relic changes
                    current_relics = self.parse_relic_value(current_clan.get('Total_Relic_Cores', '0+'))
                    previous_relics = self.parse_relic_value(previous_clan.get('Total_Relic_Cores', '0+'))
                    if current_relics != previous_relics:
                        clan_changes['relics'] = current_relics - previous_relics
                    
                    # Lunar points changes (from Grade_Score)
                    current_lunar = self.parse_lunar_points(current_clan.get('Grade_Score', '0'))
                    previous_lunar = self.parse_lunar_points(previous_clan.get('Grade_Score', '0'))
                    if current_lunar != previous_lunar:
                        clan_changes['lunar'] = current_lunar - previous_lunar
                    
                    if clan_changes:
                        changes[guild_id] = clan_changes
                        print(f"📈 {clan_name} (ID: {guild_id}): {clan_changes}")
                else:
                    # New clan
                    changes[guild_id] = {'new_clan': True}
                    print(f"🆕 New clan detected: {clan_name} (ID: {guild_id})")
            
            print(f"✅ Change calculation complete - {len(changes)} clans with changes")
            return changes
            
        except Exception as e:
            print(f"❌ Error calculating changes: {e}")
            return {}
    
    def parse_member_count(self, member_str):
        """Parse member count string like '38/40' to get current members"""
        try:
            if '/' in member_str:
                return int(member_str.split('/')[0])
            return int(member_str)
        except:
            return 0
    
    def parse_attack_value(self, attack_str):
        """Parse attack value like '41.01M' to float"""
        try:
            if 'M' in attack_str:
                return float(attack_str.replace('M', '').replace(',', '.'))
            return float(attack_str.replace(',', '.'))
        except:
            return 0.0
    
    def parse_relic_value(self, relic_str):
        """Parse relic value like '3990+' to integer"""
        try:
            return int(relic_str.replace('+', '').replace(',', ''))
        except:
            return 0
    
    def parse_lunar_points(self, lunar_str):
        """Parse lunar points from Grade_Score like '1180 +30' to base points"""
        try:
            if ' ' in lunar_str:
                return int(lunar_str.split(' ')[0])
            return int(lunar_str)
        except:
            return 0
    
    def save_historical_data(self):
        """Save current data as historical snapshot"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        try:
            # Prepare historical data structure
            historical_data = {
                'timestamp': timestamp,
                'clans': self.all_clan_data,
                'total_clans': len(self.all_clan_data),
                'total_members': len(self.all_member_data),
                'changes': self.changes_detected
            }
            
            # Save to history folder
            history_file = os.path.join(self.history_dir, f"clans_{timestamp}.json")
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(historical_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Historical data saved: {history_file}")
            
            # Also save a "latest" copy for easy access
            latest_file = os.path.join(self.history_dir, "latest_clans.json")
            with open(latest_file, 'w', encoding='utf-8') as f:
                json.dump(historical_data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving historical data: {e}")
            return False
        
    def setup_browser(self):
        """Initialize Chrome browser with optimal settings"""
        print("🔧 Setting up browser...")
        
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1400,1000")
        chrome_options.add_argument("--window-position=200,50")
        
        try:
            service = Service('/usr/bin/chromedriver')
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except:
            try:
                service = Service('/usr/local/bin/chromedriver')
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except:
                self.driver = webdriver.Chrome(options=chrome_options)
        
        self.wait = WebDriverWait(self.driver, 10)
        print("✅ Browser initialized")
    
    def load_clan_ids(self):
        """Load clan IDs with enhanced data from clan_ids.txt"""
        print("📂 Loading clan IDs with enhanced data...")
        
        if os.path.exists("clan_ids.txt"):
            try:
                clan_configs = []
                with open("clan_ids.txt", 'r') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        try:
                            # Parse: ClanID, LME_Level, Phase_Score
                            parts = [part.strip() for part in line.split(',')]
                            if len(parts) >= 3:
                                clan_id = parts[0]
                                lme_level = int(parts[1])
                                # Remove + symbol from phase score before parsing
                                phase_score_str = parts[2].replace('+', '')
                                phase_score = int(phase_score_str)
                                
                                clan_configs.append({
                                    'clan_id': clan_id,
                                    'lme_level': lme_level,
                                    'phase_score': phase_score
                                })
                            elif len(parts) == 1:
                                # Fallback for old format (just clan ID)
                                clan_configs.append({
                                    'clan_id': parts[0],
                                    'lme_level': None,
                                    'phase_score': None
                                })
                            else:
                                print(f"⚠️ Skipping invalid line {line_num}: {line}")
                                
                        except ValueError as e:
                            print(f"⚠️ Error parsing line {line_num}: {line} - {e}")
                            continue
                
                clan_ids = [config['clan_id'] for config in clan_configs]
                self.clan_configs = {config['clan_id']: config for config in clan_configs}
                
                print(f"✅ Loaded {len(clan_ids)} clan configurations")
                return clan_ids
                
            except Exception as e:
                print(f"❌ Error reading clan_ids.txt: {e}")
        
        print("📝 clan_ids.txt not found. Enter clan IDs manually:")
        clan_ids = []
        self.clan_configs = {}
        while True:
            clan_id = input(f"Clan ID #{len(clan_ids)+1} (or ENTER to finish): ").strip()
            if not clan_id:
                break
            
            try:
                lme = int(input(f"LME Level (1-16) for {clan_id}: "))
                phase = int(input(f"Phase Score for {clan_id}: "))
                clan_ids.append(clan_id)
                self.clan_configs[clan_id] = {
                    'clan_id': clan_id,
                    'lme_level': lme, 
                    'phase_score': phase
                }
            except ValueError:
                print("⚠️ Invalid input - using defaults")
                clan_ids.append(clan_id)
                self.clan_configs[clan_id] = {
                    'clan_id': clan_id,
                    'lme_level': None,
                    'phase_score': None
                }
        
        return clan_ids
    
    def create_smart_batches(self, clan_ids, batch_size=4):
        """Create batches with smart handling for 13+ clans"""
        print(f"📊 Creating smart batches for {len(clan_ids)} clan IDs...")
        
        batches = []
        
        # Create full batches of 4
        for i in range(0, len(clan_ids), batch_size):
            batch = clan_ids[i:i+batch_size]
            
            if len(batch) == batch_size:
                # Full batch of 4
                batches.append(batch)
            else:
                # Partial batch (like 13th clan) - fill with first 3 clans
                print(f"🔄 Partial batch detected: {len(batch)} clan(s)")
                
                # Add the partial clans first
                padded_batch = batch[:]
                
                # Fill remaining slots with first clans to make it 4
                needed = batch_size - len(batch)
                filler_clans = clan_ids[:needed]
                
                print(f"📝 Adding filler clans to complete batch: {filler_clans}")
                padded_batch.extend(filler_clans)
                
                batches.append(padded_batch)
        
        print(f"✅ Created {len(batches)} batches:")
        for i, batch in enumerate(batches, 1):
            print(f"   Batch {i}: {batch}")
        
        return batches
    
    def navigate_to_base_page(self):
        """Navigate to Garry Tools Lunar page"""
        try:
            print(f"🌐 Navigating to {self.base_url}")
            self.driver.get(self.base_url)
            time.sleep(3)
            return True
        except Exception as e:
            print(f"❌ Navigation failed: {e}")
            return False
    
    def fill_clan_fields(self, batch):
        """Fill clan_1, clan_2, clan_3, clan_4 fields"""
        try:
            print(f"📝 Filling clan fields: {batch}")
            
            fields = ["clan_1", "clan_2", "clan_3", "clan_4"]
            
            for i, (field_name, clan_id) in enumerate(zip(fields, batch)):
                try:
                    field_selectors = [
                        f"//input[@name='{field_name}']",
                        f"//input[@id='{field_name}']",
                        f"//input[contains(@placeholder, '{field_name}')]",
                        f"//input[contains(@class, '{field_name}')]"
                    ]
                    
                    field = None
                    for selector in field_selectors:
                        try:
                            field = self.driver.find_element(By.XPATH, selector)
                            break
                        except:
                            continue
                    
                    if field and clan_id:
                        field.clear()
                        field.send_keys(clan_id)
                        print(f"   ✅ {field_name}: {clan_id}")
                    elif not clan_id:
                        print(f"   📝 {field_name}: (empty)")
                    else:
                        print(f"   ⚠️ Could not find field: {field_name}")
                        
                except Exception as e:
                    print(f"   ❌ Error filling {field_name}: {e}")
                    continue
            
            return True
            
        except Exception as e:
            print(f"❌ Error filling clan fields: {e}")
            return False
    
    def click_submit(self):
        """Click the Show Details button"""
        try:
            print("🎯 Clicking Show Details button...")
            
            submit_selectors = [
                "//button[contains(text(), 'Show Details')]",
                "//button[@type='submit' and contains(@class, 'btn-success')]",
                "//button[@type='submit' and contains(text(), 'Show Details')]",
                "//button[contains(@class, 'btn-success')]",
                "//button[@type='submit']"
            ]
            
            for i, selector in enumerate(submit_selectors, 1):
                try:
                    submit_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    submit_btn.click()
                    print(f"✅ Submit button clicked")
                    time.sleep(5)
                    return True
                except:
                    continue
            
            print("❌ Submit button not found")
            return False
            
        except Exception as e:
            print(f"❌ Submit error: {e}")
            return False
    
    def extract_clan_summary_data(self):
        """Extract main clan statistics from the summary table"""
        print("📊 Extracting clan summary data...")
        clan_data = []
        
        try:
            main_table = self.driver.find_element(By.XPATH, "//table[contains(@class, 'table-hover')]//tbody")
            clan_rows = main_table.find_elements(By.XPATH, ".//tr")
            
            print(f"📋 Found {len(clan_rows)} clan rows")
            
            for i, row in enumerate(clan_rows):
                try:
                    cells = row.find_elements(By.XPATH, ".//td")
                    
                    if len(cells) >= 8:
                        global_rank = cells[0].text.strip()
                        guild_id = cells[1].text.strip()
                        name = cells[2].text.strip()
                        level = cells[3].text.strip()
                        grade = cells[4].text.strip()
                        grade_score = cells[5].text.strip()
                        total_relic_cores = cells[6].text.strip()
                        total_attack = cells[7].text.strip()
                        
                        # Check if this clan ID has already been processed
                        if guild_id in self.processed_clan_ids:
                            print(f"   🔄 Skipping duplicate: {name} (ID: {guild_id}) - already processed")
                            continue
                        
                        # Mark this clan ID as processed
                        self.processed_clan_ids.add(guild_id)
                        
                        clan_info = {
                            'Batch': self.batch_count,
                            'Global_Rank': global_rank,
                            'Guild_ID': guild_id,
                            'Name': name,
                            'Level': level,
                            'Grade': grade,
                            'Grade_Score': grade_score,
                            'Total_Relic_Cores': total_relic_cores,
                            'Total_Attack': total_attack,
                            'Member_Count': 0,  # Will be updated after member extraction
                            'Extraction_Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        
                        clan_data.append(clan_info)
                        print(f"   ✅ {name} (Rank: {global_rank}, ID: {guild_id})")
                    
                except Exception as e:
                    print(f"   ⚠️ Error processing clan row {i+1}: {e}")
                    continue
            
            print(f"✅ Extracted {len(clan_data)} NEW clan records")
            return clan_data
            
        except Exception as e:
            print(f"❌ Error extracting clan data: {e}")
            return []
    
    def extract_member_data_from_page(self, data_type="Relic Cores"):
        """Extract member data from current page"""
        print(f"👥 Extracting {data_type} data...")
        all_members = []
        clan_member_counts = {}
        
        try:
            clan_containers = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'col-lg-3')]//table")
            print(f"📋 Found {len(clan_containers)} clan member tables")
            
            for table_idx, table in enumerate(clan_containers):
                try:
                    clan_name_element = table.find_element(By.XPATH, ".//th[@colspan='10']")
                    clan_name = clan_name_element.text.strip()
                    
                    member_rows = table.find_elements(By.XPATH, ".//tbody//tr")
                    member_count = 0
                    
                    for row in member_rows:
                        try:
                            cells = row.find_elements(By.XPATH, ".//td")
                            
                            if len(cells) >= 3:
                                position = cells[0].text.strip()
                                member_name = cells[1].text.strip()
                                stat_value = cells[2].text.strip()
                                
                                if not position.isdigit():
                                    continue
                                
                                member_info = {
                                    'Clan_Name': clan_name,
                                    'Position': position,
                                    'Member_Name': member_name,
                                    'Stat_Value': stat_value
                                }
                                
                                all_members.append(member_info)
                                member_count += 1
                        
                        except Exception as e:
                            continue
                    
                    clan_member_counts[clan_name] = member_count
                    print(f"   🎯 {clan_name}: {member_count}/40 members")
                    
                except Exception as e:
                    print(f"   ⚠️ Error processing table {table_idx+1}: {e}")
                    continue
            
            print(f"✅ Total {data_type} extracted: {len(all_members)} members")
            return all_members, clan_member_counts
            
        except Exception as e:
            print(f"❌ Error extracting {data_type} data: {e}")
            return [], {}
    
    def extract_complete_member_data(self):
        """Extract both Attack and Relic Cores data for all members"""
        print("\n⚔️ Extracting COMPLETE member intelligence...")
        
        # Step 1: Get Attack data (page defaults to this after submit)
        print("📊 Step 1: Extracting Attack data (default page)...")
        attack_members, member_counts = self.extract_member_data_from_page("Attack")
        
        # Step 2: Switch to Relic Cores page by adding type=core
        current_url = self.driver.current_url
        if "type=core" not in current_url:
            # Add type=core to URL
            if "?" in current_url:
                relic_url = current_url + "&type=core"
            else:
                relic_url = current_url + "?type=core"
        else:
            relic_url = current_url
        
        print(f"🌐 Step 2: Switching to Relic Cores data...")
        print(f"   {relic_url}")
        
        try:
            self.driver.get(relic_url)
            time.sleep(5)
            
            # Step 3: Get Relic Cores data
            relic_members, _ = self.extract_member_data_from_page("Relic Cores")
            
            # Step 4: Combine the data intelligently (Attack first, then add Relic data)
            print("🔄 Combining Attack and Relic Cores intelligence...")
            combined_members = []
            matches_found = 0
            
            for attack_member in attack_members:
                # Match by clan and member name only (rankings differ between pages)
                matching_relic = None
                for relic_member in relic_members:
                    if (relic_member['Clan_Name'] == attack_member['Clan_Name'] and 
                        relic_member['Member_Name'] == attack_member['Member_Name']):
                        matching_relic = relic_member
                        matches_found += 1
                        break
                
                combined_member = {
                    'Batch': self.batch_count,
                    'Clan_Name': attack_member['Clan_Name'],
                    'Attack_Position': attack_member['Position'],
                    'Relic_Position': matching_relic['Position'] if matching_relic else 'N/A',
                    'Member_Name': attack_member['Member_Name'],
                    'Attack': attack_member['Stat_Value'],
                    'Relic_Cores': matching_relic['Stat_Value'] if matching_relic else 'N/A',
                    'Extraction_Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                combined_members.append(combined_member)
            
            print(f"✅ Combined intelligence for {len(combined_members)} members")
            print(f"🎯 Relic data matches: {matches_found}/{len(attack_members)}")
            
            return combined_members, member_counts
            
        except Exception as e:
            print(f"❌ Error extracting relic data: {e}")
            # Return attack data only if relic extraction fails
            attack_only_members = []
            for attack_member in attack_members:
                combined_member = {
                    'Batch': self.batch_count,
                    'Clan_Name': attack_member['Clan_Name'],
                    'Attack_Position': attack_member['Position'],
                    'Relic_Position': 'N/A',
                    'Member_Name': attack_member['Member_Name'],
                    'Attack': attack_member['Stat_Value'],
                    'Relic_Cores': 'N/A',
                    'Extraction_Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                attack_only_members.append(combined_member)
            return attack_only_members, member_counts
    
    def update_clan_member_counts(self, clan_data, member_counts):
        """Update clan data with actual member counts"""
        for clan in clan_data:
            clan_name = clan['Name']
            # Find matching member count (clan names might have slight differences)
            for count_name, count in member_counts.items():
                if clan_name.upper() == count_name.upper():
                    clan['Member_Count'] = f"{count}/40"
                    break
            else:
                clan['Member_Count'] = "Unknown/40"
    
    def process_batch(self, batch, batch_num, total_batches):
        """Process a single batch of 4 clan IDs"""
        print(f"\n{'='*25} BATCH {batch_num}/{total_batches} {'='*25}")
        print(f"🎯 Processing clans: {batch}")
        
        self.batch_count = batch_num
        
        # Navigate to base page
        if not self.navigate_to_base_page():
            return False, [], []
        
        # Fill clan fields
        if not self.fill_clan_fields(batch):
            return False, [], []
        
        # Submit
        if not self.click_submit():
            return False, [], []
        
        # Extract clan summary data
        clan_data = self.extract_clan_summary_data()
        
        # Extract complete member data (both Relic Cores and Attack)
        member_data, member_counts = self.extract_complete_member_data()
        
        # Update clan data with member counts
        self.update_clan_member_counts(clan_data, member_counts)
        
        # Add to global collections, filtering duplicates for member data too
        self.all_clan_data.extend(clan_data)
        
        # Filter member data to avoid duplicates from filler clans
        new_member_data = []
        for member in member_data:
            # Create unique identifier for member (clan + name)
            member_key = f"{member['Clan_Name']}_{member['Member_Name']}"
            
            # Check if we've already recorded this member
            already_exists = any(
                f"{existing['Clan_Name']}_{existing['Member_Name']}" == member_key 
                for existing in self.all_member_data
            )
            
            if not already_exists:
                new_member_data.append(member)
        
        self.all_member_data.extend(new_member_data)
        
        print(f"✅ Batch {batch_num} completed successfully")
        print(f"   📊 NEW Clans: {len(clan_data)}")
        print(f"   👥 NEW Members: {len(new_member_data)}")
        if len(new_member_data) < len(member_data):
            print(f"   🔄 Filtered out {len(member_data) - len(new_member_data)} duplicate members from filler clans")
        
        return True, clan_data, member_data
    
    def enhance_clan_data_with_configs(self):
        """Enhance clan data with LME level and phase score from configs"""
        for clan in self.all_clan_data:
            guild_id = clan['Guild_ID']
            if guild_id in self.clan_configs:
                config = self.clan_configs[guild_id]
                clan['LME_Level'] = config['lme_level']
                clan['Phase_Score'] = config['phase_score']
            else:
                clan['LME_Level'] = None
                clan['Phase_Score'] = None
    
    def save_to_javascript(self):
        """Save data to JavaScript files for web dashboard with change tracking"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Enhance clan data with LME and phase data
            self.enhance_clan_data_with_configs()
            
            # Generate clansData.js with change data
            if self.all_clan_data:
                clan_js_filename = "clansData.js"
                with open(clan_js_filename, 'w', encoding='utf-8') as f:
                    f.write("// Clan Intelligence Data\n")
                    f.write(f"// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"// Total Clans: {len(self.all_clan_data)}\n\n")
                    
                    f.write("const clansData = ")
                    f.write(json.dumps(self.all_clan_data, indent=2, ensure_ascii=False))
                    f.write(";\n\n")
                    
                    # Add metadata with change information
                    metadata = {
                        "lastUpdated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "totalClans": len(self.all_clan_data),
                        "totalMembers": len(self.all_member_data),
                        "dataCompleteness": len([m for m in self.all_member_data if m['Attack'] != 'N/A']),
                        "version": "1.1",
                        "hasChanges": bool(self.changes_detected),
                        "changeCount": len(self.changes_detected)
                    }
                    
                    f.write("const clansMetadata = ")
                    f.write(json.dumps(metadata, indent=2))
                    f.write(";\n\n")
                    
                    # Add changes data
                    f.write("const clansChanges = ")
                    f.write(json.dumps(self.changes_detected, indent=2, ensure_ascii=False))
                    f.write(";\n\n")
                    
                    f.write("// Export for ES6 modules\n")
                    f.write("if (typeof module !== 'undefined' && module.exports) {\n")
                    f.write("  module.exports = { clansData, clansMetadata, clansChanges };\n")
                    f.write("}\n")
                
                print(f"✅ Clan data saved: {clan_js_filename}")
                if self.changes_detected:
                    print(f"📈 Change data included: {len(self.changes_detected)} clans with changes")
            
            # Generate membersData.js
            if self.all_member_data:
                member_js_filename = "membersData.js"
                with open(member_js_filename, 'w', encoding='utf-8') as f:
                    f.write("// Member Intelligence Data\n")
                    f.write(f"// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"// Total Members: {len(self.all_member_data)}\n\n")
                    
                    f.write("const membersData = ")
                    f.write(json.dumps(self.all_member_data, indent=2, ensure_ascii=False))
                    f.write(";\n\n")
                    
                    # Add member statistics
                    member_stats = {
                        "totalMembers": len(self.all_member_data),
                        "clanCount": len(set(m['Clan_Name'] for m in self.all_member_data)),
                        "attackDataComplete": len([m for m in self.all_member_data if m['Attack'] != 'N/A']),
                        "relicDataComplete": len([m for m in self.all_member_data if m['Relic_Cores'] != 'N/A']),
                        "lastUpdated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    f.write("const membersMetadata = ")
                    f.write(json.dumps(member_stats, indent=2))
                    f.write(";\n\n")
                    
                    f.write("// Export for ES6 modules\n")
                    f.write("if (typeof module !== 'undefined' && module.exports) {\n")
                    f.write("  module.exports = { membersData, membersMetadata };\n")
                    f.write("}\n")
                
                print(f"✅ Member data saved: {member_js_filename}")
            
            # Copy files to current directory for dashboard
            try:
                if os.path.exists("clansData.js"):
                    shutil.copy("clansData.js", os.path.join(self.current_dir, "clansData.js"))
                if os.path.exists("membersData.js"):
                    shutil.copy("membersData.js", os.path.join(self.current_dir, "membersData.js"))
                print(f"📁 Files copied to {self.current_dir}")
            except Exception as e:
                print(f"⚠️ Warning: Could not copy to current directory: {e}")
            
            return timestamp
            
        except Exception as e:
            print(f"❌ JavaScript export error: {e}")
            return None
    
    def run_intelligence_gathering(self, clan_ids):
        """Main intelligence gathering process with historical tracking"""
        print("🎮 LUNAR CLAN INTELLIGENCE SYSTEM - Enhanced Edition")
        print("=" * 70)
        print(f"🎯 Target clans: {len(clan_ids)}")
        print(f"📊 Intelligence: Clan stats + Member profiles (Relic & Attack)")
        print(f"📈 Historical: Change tracking enabled")
        print("=" * 70)
        
        # Load previous data for comparison
        self.previous_data = self.load_previous_data()
        
        # Setup browser
        self.setup_browser()
        
        # Create smart batches
        batches = self.create_smart_batches(clan_ids)
        
        print(f"\n🚀 Starting intelligence gathering...")
        print(f"📦 Processing {len(batches)} batches")
        
        successful_batches = 0
        
        for i, batch in enumerate(batches, 1):
            try:
                success, clan_data, member_data = self.process_batch(batch, i, len(batches))
                if success:
                    successful_batches += 1
                else:
                    print(f"❌ Batch {i} failed")
                    
            except KeyboardInterrupt:
                print(f"\n⏹️ Intelligence gathering stopped by user")
                break
            except Exception as e:
                print(f"❌ Batch {i} error: {e}")
                continue
        
        # Calculate changes from previous data
        if self.all_clan_data:
            self.changes_detected = self.calculate_changes(self.all_clan_data)
        
        # Save historical snapshot only if all batches completed successfully
        if self.all_clan_data:
            if successful_batches == len(batches):
                self.save_historical_data()
            else:
                print(f"⚠️ History NOT saved - only {successful_batches}/{len(batches)} batches completed. Fix your connection and rerun.")
        
        # Save intelligence data in multiple formats
        csv_timestamp = None
        js_timestamp = None
        
        if self.all_clan_data or self.all_member_data:
            # Save CSV files for backup/analysis
            csv_timestamp = self.save_to_csv()
            
            # Save JavaScript files for web dashboard (with change data)
            js_timestamp = self.save_to_javascript()
        
        # Print change summary
        if self.changes_detected:
            print(f"\n📈 CHANGE SUMMARY")
            print("=" * 50)
            
            # Create a Guild_ID to Name mapping for display
            clan_name_map = {clan['Guild_ID']: clan['Name'] for clan in self.all_clan_data}
            
            for guild_id, changes in self.changes_detected.items():
                clan_name = clan_name_map.get(guild_id, f"Guild {guild_id}")
                
                if changes.get('new_clan'):
                    print(f"🆕 {clan_name}: NEW CLAN DETECTED")
                else:
                    change_parts = []
                    if 'members' in changes:
                        change_parts.append(f"Members: {changes['members']:+d}")
                    if 'rank' in changes:
                        change_parts.append(f"Rank: {changes['rank']:+d}")
                    if 'attack' in changes:
                        change_parts.append(f"Attack: {changes['attack']:+.1f}M")
                    if 'relics' in changes:
                        change_parts.append(f"Relics: {changes['relics']:+d}")
                    if 'lunar' in changes:
                        change_parts.append(f"Lunar: {changes['lunar']:+d}")
                    
                    if change_parts:
                        print(f"📊 {clan_name}: {', '.join(change_parts)}")
            print("=" * 50)
    
    def save_to_csv(self):
        """Save all data to CSV files (backup format)"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Enhance clan data first
            self.enhance_clan_data_with_configs()
            
            # Save clan data
            if self.all_clan_data:
                clan_filename = f"lunar_clan_intelligence_{timestamp}.csv"
                with open(clan_filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=self.all_clan_data[0].keys())
                    writer.writeheader()
                    writer.writerows(self.all_clan_data)
                print(f"✅ Clan CSV saved: {clan_filename}")
            
            # Save member data
            if self.all_member_data:
                member_filename = f"lunar_member_intelligence_{timestamp}.csv"
                with open(member_filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=self.all_member_data[0].keys())
                    writer.writeheader()
                    writer.writerows(self.all_member_data)
                print(f"✅ Member CSV saved: {member_filename}")
            
            return timestamp
            
        except Exception as e:
            print(f"❌ CSV save error: {e}")
            return None
        
        # Final intelligence report
        print(f"\n{'='*70}")
        print(f"🎖️  INTELLIGENCE GATHERING COMPLETE")
        print(f"{'='*70}")
        print(f"✅ Successful batches: {successful_batches}/{len(batches)}")
        print(f"🏰 Clans analyzed: {len(self.all_clan_data)}")
        print(f"👥 Members profiled: {len(self.all_member_data)}")
        print(f"📊 Data completeness: {len([m for m in self.all_member_data if m['Attack'] != 'N/A'])}/{len(self.all_member_data)} with attack data")
        print(f"📈 Changes detected: {len(self.changes_detected)} clans with changes")
        if csv_timestamp:
            print(f"💾 CSV files: lunar_*_intelligence_{csv_timestamp}.csv")
        if js_timestamp:
            print(f"🌐 Web files: clansData.js + membersData.js (with changes)")
            print(f"🚀 Ready for GitHub Pages deployment!")
        print(f"🗂️ Historical data: {self.history_dir}")
        print(f"{'='*70}")
        
        return successful_batches > 0
    
    def cleanup(self):
        """Close browser and cleanup"""
        if self.driver:
            print("🔒 Closing browser...")
            self.driver.quit()

def main():
    print("🌙 Lunar Clan Intelligence System - Enhanced with Historical Tracking")
    print("=" * 70)
    print("🎯 Features:")
    print("   • Smart batching (handles 13+ clans perfectly)")
    print("   • Complete clan stats + member intelligence")
    print("   • Both Relic Cores AND Attack data")
    print("   • HISTORICAL CHANGE TRACKING - Compare with previous runs")
    print("   • Professional CSV export + Web dashboard")
    print("   • Robust error handling")
    print("=" * 70)
    
    scraper = LunarIntelligenceSystem()
    
    try:
        # Load clan IDs
        clan_ids = scraper.load_clan_ids()
        if not clan_ids:
            print("❌ No clan IDs to process")
            return
        
        # Final confirmation
        print(f"\n📊 Ready to gather intelligence on {len(clan_ids)} clans")
        confirm = input(f"🚀 Start intelligence gathering? (y/n) [y]: ").strip().lower()
        if confirm and confirm != 'y':
            print("❌ Intelligence gathering cancelled")
            return
        
        # Run intelligence gathering
        success = scraper.run_intelligence_gathering(clan_ids)
        
        if success:
            print("\n🎉 Intelligence gathering completed successfully!")
            print("📈 Data ready for competitive analysis!")
        else:
            print("\n⚠️ Intelligence gathering had issues - check logs")
        
    except KeyboardInterrupt:
        print(f"\n⏹️ Interrupted")
    except Exception as e:
        print(f"❌ System error: {e}")
    finally:
        scraper.cleanup()

if __name__ == "__main__":
    main()
