#!/usr/bin/env python3
"""
Maccabi Activity Schedule Scraper
=================================

This script automatically navigates through the Maccabi app and extracts
detailed schedule information for all available activities.

Usage: python3 maccabi_activity_scraper.py

Requirements:
- Android emulator running with Maccabi app
- ADB configured and accessible
- App should be on the main activities list screen
"""

import subprocess
import time
import xml.etree.ElementTree as ET
import html
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

class MaccabiScraper:
    def __init__(self):
        self.results = []
        self.failed_activities = []
        self.current_activity_index = 0
        self.max_retries = 3
        self.wait_time = 3  # Base wait time, but we'll use adaptive waiting
        self.start_time = time.time()  # Initialize start time immediately
        self.last_save_time = None
        self.output_filename = None  # Will be set once and reused
        
        # In-memory activity state management
        self.discovered_activities = {}  # activity_name -> activity_data
        self.processed_activities = set()  # activity_names that are fully processed
        self.failed_activity_names = set()  # activity_names that failed processing
        
        # MAP BUTTON PROTECTION - NEVER CLICK THESE COORDINATES!
        self.dangerous_map_button = {
            'description': 'מפה',  # Hebrew for "map"
            'top_y': 1803,  # Top of map button from UI hierarchy [388,1803][692,1908]
            'min_x': 350, 'max_x': 730,  # Expanded safety zone around map button
            'min_y': 1750, 'max_y': 1950,  # Expanded safety zone around map button
            'exact_bounds': '[388,1803][692,1908]'  # Exact bounds from UI hierarchy
        }
        print(f"🛡️ MAP BUTTON PROTECTION ENABLED - Map button top Y: {self.dangerous_map_button['top_y']}")
        print(f"🛡️ Will only click activities whose BOTTOM edge is ABOVE Y={self.dangerous_map_button['top_y']}")
        
    def run_adb_command(self, command: str) -> Tuple[bool, str]:
        """Execute ADB command and return success status and output"""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            print(f"⚠️ Command timed out: {command}")
            return False, ""
        except Exception as e:
            print(f"❌ Command failed: {command} - {e}")
            return False, ""
    
    def capture_screen(self, filename: str) -> Optional[ET.Element]:
        """Capture UI hierarchy and return parsed XML root"""
        dump_cmd = f"adb shell uiautomator dump /sdcard/{filename}.xml"
        pull_cmd = f"adb pull /sdcard/{filename}.xml /tmp/{filename}.xml"
        
        success, _ = self.run_adb_command(dump_cmd)
        if not success:
            print(f"❌ Failed to dump UI for {filename}")
            return None
            
        success, _ = self.run_adb_command(pull_cmd)
        if not success:
            print(f"❌ Failed to pull UI dump for {filename}")
            return None
            
        try:
            tree = ET.parse(f'/tmp/{filename}.xml')
            return tree.getroot()
        except Exception as e:
            print(f"❌ Failed to parse XML for {filename}: {e}")
            return None
    
    def wait_for_content_load(self, expected_content_type: str = "general", max_wait: int = 10) -> bool:
        """Smart waiting that checks for content loading and stops early when ready"""
        print(f"⏳ Waiting for {expected_content_type} content to load (max {max_wait}s)...")
        
        start_time = time.time()
        check_interval = 0.5  # Check every 500ms
        
        while time.time() - start_time < max_wait:
            # Capture current state to check if content is loaded
            root = self.capture_screen_quick("loading_check")
            if root is None:
                time.sleep(check_interval)
                continue
            
            # Check for different types of loaded content
            if expected_content_type == "activity_list":
                if self.is_activity_list_loaded(root):
                    elapsed = time.time() - start_time
                    print(f"✅ Activity list loaded in {elapsed:.1f}s")
                    return True
            elif expected_content_type == "activity_detail":
                if self.is_activity_detail_loaded(root):
                    elapsed = time.time() - start_time
                    print(f"✅ Activity detail loaded in {elapsed:.1f}s")
                    return True
            elif expected_content_type == "schedule":
                if self.is_schedule_loaded(root):
                    elapsed = time.time() - start_time
                    print(f"✅ Schedule loaded in {elapsed:.1f}s")
                    return True
            else:  # general content
                if self.is_general_content_loaded(root):
                    elapsed = time.time() - start_time
                    print(f"✅ Content loaded in {elapsed:.1f}s")
                    return True
            
            time.sleep(check_interval)
        
        print(f"⚠️ Timeout waiting for {expected_content_type} content ({max_wait}s)")
        return False
    
    def capture_screen_quick(self, filename: str) -> Optional[ET.Element]:
        """Quick screen capture without file operations for loading checks"""
        try:
            dump_cmd = f"adb shell uiautomator dump /sdcard/{filename}_quick.xml"
            pull_cmd = f"adb pull /sdcard/{filename}_quick.xml /tmp/{filename}_quick.xml"
            
            result = subprocess.run(dump_cmd, shell=True, capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return None
                
            result = subprocess.run(pull_cmd, shell=True, capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return None
            
            tree = ET.parse(f'/tmp/{filename}_quick.xml')
            return tree.getroot()
        except:
            return None
    
    def is_activity_list_loaded(self, root: ET.Element) -> bool:
        """Check if activity list screen is fully loaded"""
        descriptions = self.extract_all_descriptions(root)
        all_text = ' '.join(descriptions)
        
        # Look for activity indicators that show the list is loaded
        activity_indicators = ['₪', 'תל אביב', 'רמת גן', 'פילאטיס', 'יוגה', 'סטודיו']
        has_activities = sum(1 for indicator in activity_indicators if indicator in all_text) >= 2
        
        # Also check we're not seeing loading indicators
        loading_indicators = ['טוען', 'Loading', 'מעמיס']
        is_loading = any(indicator in all_text for indicator in loading_indicators)
        
        return has_activities and not is_loading
    
    def is_activity_detail_loaded(self, root: ET.Element) -> bool:
        """Check if activity detail screen is fully loaded"""
        descriptions = self.extract_all_descriptions(root)
        clickable_elements = self.extract_clickable_elements(root)
        
        # Look for detail screen indicators
        has_schedule_button = any('לוח פעילויות' in elem['desc'] for elem in clickable_elements)
        has_detail_content = any(len(desc) > 50 for desc in descriptions)  # Detailed descriptions
        
        # Check we're not seeing loading indicators
        all_text = ' '.join(descriptions)
        loading_indicators = ['טוען', 'Loading', 'מעמיס']
        is_loading = any(indicator in all_text for indicator in loading_indicators)
        
        return (has_schedule_button or has_detail_content) and not is_loading
    
    def has_no_events_for_day(self, root: ET.Element) -> bool:
        """Check if we're seeing the 'no events' screen for current day"""
        descriptions = self.extract_all_descriptions(root)
        all_text = ' '.join(descriptions)
        
        # Look for "no events" indicators
        no_events_indicators = [
            'אין לנו אימונים ביום הזה',  # We don't have training sessions on this day
            'אפשר לחפש ביום אחר',       # You can search on another day
            'אין אימונים',              # No training sessions
            'אין פעילויות'              # No activities
        ]
        
        return any(indicator in all_text for indicator in no_events_indicators)
    
    def is_schedule_loaded(self, root: ET.Element) -> bool:
        """Check if schedule screen is fully loaded"""
        descriptions = self.extract_all_descriptions(root)
        all_text = ' '.join(descriptions)
        
        # First check if it's a "no events" screen - this is also "loaded"
        if self.has_no_events_for_day(root):
            return True
        
        # Look for schedule indicators
        has_calendar = any(day in all_text for day in ['ראשון', 'שני', 'שלישי'])
        has_times = any(':' in desc and '-' in desc for desc in descriptions)
        
        # Check we're not seeing loading indicators
        loading_indicators = ['טוען', 'Loading', 'מעמיס']
        is_loading = any(indicator in all_text for indicator in loading_indicators)
        
        return has_calendar and has_times and not is_loading
    
    def is_general_content_loaded(self, root: ET.Element) -> bool:
        """Check if general content is loaded (not a loading screen)"""
        descriptions = self.extract_all_descriptions(root)
        clickable_elements = self.extract_clickable_elements(root)
        
        # Simple check: do we have reasonable amount of content?
        has_content = len(descriptions) > 5 or len(clickable_elements) > 3
        
        # Check we're not seeing loading indicators
        all_text = ' '.join(descriptions)
        loading_indicators = ['טוען', 'Loading', 'מעמיס']
        is_loading = any(indicator in all_text for indicator in loading_indicators)
        
        return has_content and not is_loading
    
    def get_screen_signature(self, root: ET.Element) -> str:
        """Get a signature of the screen content for comparison"""
        try:
            # Get all clickable element descriptions and their rough positions
            clickable_elements = self.extract_clickable_elements(root)
            
            # Create a signature based on clickable elements (activities)
            signature_parts = []
            for elem in clickable_elements:
                desc = elem['desc'][:50]  # First 50 chars
                bounds = elem['bounds']
                signature_parts.append(f"{desc}_{bounds}")
            
            # Sort to ensure consistent comparison
            signature_parts.sort()
            return "|".join(signature_parts)
        except:
            return "unknown"
    
    def is_at_bottom_of_list(self, root: ET.Element) -> bool:
        """Check if we're at the bottom of the activities list"""
        descriptions = self.extract_all_descriptions(root)
        all_text = ' '.join(descriptions)
        
        # Look for bottom indicators in Hebrew/English
        bottom_indicators = [
            'סוף הרשימה',  # End of list
            'אין עוד',        # No more
            'זה הכל',         # That's all
            'end of list',
            'no more items',
            'bottom',
            'סיים'             # Finished
        ]
        
        # Check for typical bottom-of-list indicators
        has_bottom_indicator = any(indicator in all_text.lower() for indicator in bottom_indicators)
        
        # Additional check: if we have very few activities on screen, might be at bottom
        activities = self.find_activities_on_screen(root)
        has_few_activities = len(activities) <= 2
        
        # Look for UI elements that typically appear at the bottom
        clickable_elements = self.extract_clickable_elements(root)
        bottom_ui_elements = ['חזרה', 'back', 'home', 'דף הבית']
        has_bottom_ui = any(any(ui_elem in elem['desc'].lower() for ui_elem in bottom_ui_elements) for elem in clickable_elements)
        
        return has_bottom_indicator or (has_few_activities and has_bottom_ui)
    
    def tap_element(self, x: int, y: int, description: str = "") -> bool:
        """Tap at coordinates and wait smartly for content to load"""
        print(f"🖱️ Tapping at ({x}, {y}) - {description}")
        success, _ = self.run_adb_command(f"adb shell input tap {x} {y}")
        
        # Smart waiting based on what we expect to load
        if "activity" in description.lower() and "schedule" not in description.lower():
            self.wait_for_content_load("activity_detail", max_wait=15)  # Increased from 8 to 15 seconds
        elif "schedule" in description.lower():
            self.wait_for_content_load("schedule", max_wait=12)  # Increased from 6 to 12 seconds
        else:
            self.wait_for_content_load("general", max_wait=10)  # Increased from 5 to 10 seconds
        
        return success
    
    def go_back(self) -> bool:
        """Press back button and wait smartly for transition"""
        print("⬅️ Going back")
        success, _ = self.run_adb_command("adb shell input keyevent 4")
        
        # Smart waiting for back navigation - expect to return to activity list
        self.wait_for_content_load("activity_list", max_wait=12)  # Increased from 8 to 12 seconds
        return success
    
    def extract_clickable_elements(self, root: ET.Element) -> List[Dict]:
        """Extract all clickable elements with their descriptions and bounds"""
        elements = []
        for elem in root.iter('node'):
            if elem.get('clickable') == 'true':
                desc = elem.get('content-desc', '').strip()
                bounds = elem.get('bounds', '')
                if desc:
                    elements.append({
                        'desc': html.unescape(desc),
                        'bounds': bounds,
                        'class': elem.get('class', '')
                    })
        return elements
    
    def extract_all_descriptions(self, root: ET.Element) -> List[str]:
        """Extract all content descriptions from UI"""
        descriptions = []
        for elem in root.iter('node'):
            desc = elem.get('content-desc', '').strip()
            if desc:
                descriptions.append(html.unescape(desc))
        return descriptions
    
    def parse_bounds(self, bounds_str: str) -> Tuple[int, int]:
        """Parse bounds string and return center coordinates"""
        try:
            # Format: [x1,y1][x2,y2]
            import re
            # Use regex to extract coordinates more reliably
            coords = re.findall(r'\[(\d+),(\d+)\]', bounds_str)
            if len(coords) >= 2:
                x1, y1 = map(int, coords[0])
                x2, y2 = map(int, coords[1])
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                return center_x, center_y
            return 0, 0
        except Exception as e:
            print(f"⚠️ Failed to parse bounds: {bounds_str} - {e}")
            return 0, 0
    
    def update_activity_discovery(self, screen_activities: List[Dict]) -> None:
        """Update the discovered activities map with new activities found on screen"""
        for activity in screen_activities:
            activity_name = activity['description'].split('\n')[0] if '\n' in activity['description'] else activity['description']
            
            # Always update coordinates (activities might shift during scrolling)
            if activity_name not in self.discovered_activities:
                print(f"📍 Discovered new activity: {activity_name[:50]}...")
            else:
                # Update coordinates if activity moved
                old_coords = (self.discovered_activities[activity_name]['x'], self.discovered_activities[activity_name]['y'])
                new_coords = (activity['x'], activity['y'])
                if old_coords != new_coords:
                    print(f"📍 Updated coordinates for {activity_name[:30]}...: {old_coords} -> {new_coords}")
            
            self.discovered_activities[activity_name] = activity
    
    def get_next_unprocessed_activity(self) -> Optional[Dict]:
        """Get the next activity that hasn't been processed yet"""
        for activity_name, activity_data in self.discovered_activities.items():
            if (activity_name not in self.processed_activities and 
                activity_name not in self.failed_activity_names):
                return activity_data
        return None
    
    def mark_activity_processed(self, activity_name: str) -> None:
        """Mark an activity as successfully processed"""
        self.processed_activities.add(activity_name)
        print(f"✅ Marked as processed: {activity_name[:40]}...")
    
    def mark_activity_failed(self, activity_name: str) -> None:
        """Mark an activity as failed to process"""
        self.failed_activity_names.add(activity_name)
        print(f"❌ Marked as failed: {activity_name[:40]}...")
    
    def get_discovery_stats(self) -> Dict:
        """Get statistics about discovered vs processed activities"""
        total_discovered = len(self.discovered_activities)
        total_processed = len(self.processed_activities)
        total_failed = len(self.failed_activity_names)
        remaining = total_discovered - total_processed - total_failed
        
        return {
            'discovered': total_discovered,
            'processed': total_processed,
            'failed': total_failed,
            'remaining': remaining
        }
    def find_activities_on_screen(self, root: ET.Element) -> List[Dict]:
        """Find activity items on the current screen - improved detection with less strict filtering"""
        activities = []
        clickable_elements = self.extract_clickable_elements(root)
        
        print(f"🔍 Scanning {len(clickable_elements)} clickable elements for activities...")
        
        for elem in clickable_elements:
            # Skip the dangerous map button
            if elem['bounds'] == self.dangerous_map_button['exact_bounds']:
                print("⚠️ Skipping dangerous map button (exact match)")
                continue
            
            # Parse bounds to check if element overlaps with map button area
            try:
                import re
                coords = re.findall(r'\[(\d+),(\d+)\]', elem['bounds'])
                if len(coords) >= 2:
                    x1, y1 = map(int, coords[0])  # Top-left corner
                    x2, y2 = map(int, coords[1])  # Bottom-right corner
                    
                    # Check if this element's BOTTOM edge is BELOW the map button's TOP edge
                    # If so, skip it to avoid any overlap with map button
                    if y2 >= self.dangerous_map_button['top_y']:
                        elem_desc = elem['desc'][:30] if elem['desc'] else 'Unknown element'
                        print(f"⚠️ Skipping element '{elem_desc}...' - bottom edge Y={y2} overlaps with map button (top Y={self.dangerous_map_button['top_y']})")
                        continue
                    
                    # Additional safety check for elements in the general map button area
                    if (self.dangerous_map_button['min_x'] <= x1 <= self.dangerous_map_button['max_x'] and
                        self.dangerous_map_button['min_y'] <= y1 <= self.dangerous_map_button['max_y']):
                        print(f"⚠️ Skipping element '{elem_desc}...' - in map button safety zone")
                        continue
                        
            except Exception as e:
                print(f"⚠️ Error parsing bounds {elem['bounds']}: {e}")
                # If we can't parse bounds, skip the element to be safe
                continue
            desc = elem['desc']
            
            # SIMPLIFIED FILTERING: Only block obvious navigation elements
            navigation_keywords = [
                'מפה', 'map', 'דף הבית', 'upmind', 'upbody', 'upshop',
                'חיפוש', 'search', 'בטל', 'אישור', 'סגור'
            ]
            
            # Quick navigation check
            desc_lower = desc.lower().strip()
            is_navigation = any(nav in desc_lower for nav in navigation_keywords)
            
            if is_navigation:
                continue
            
            # Skip very short descriptions (likely buttons)
            if len(desc.strip()) < 15:
                continue
            
            # RELAXED ACTIVITY DETECTION: Look for key activity indicators
            has_price = '₪' in desc
            has_multiple_lines = len(desc.split('\n')) >= 2  # Reduced from 3 to 2
            
            # Location indicators (cities, neighborhoods, streets)
            location_indicators = [
                'תל אביב', 'רמת גן', 'פתח תקווה', 'הרצליה', 'רחובות', 'ראשון לציון',
                'חולון', 'בת ים', 'גבעתיים', 'יהוד', 'אור יהודה', 'כפר סבא',
                'דיזנגוף', 'רוטשילד', 'נחלת בנימין', 'פלורנטין', 'יפו', 'נווה צדק',
                'רח\'', 'רחוב', 'שד\'', 'שדרות'
            ]
            has_location = any(location in desc for location in location_indicators)
            
            # Activity type indicators
            activity_keywords = [
                'סטודיו', 'פילאטיס', 'יוגה', 'פיטנס', 'אימון', 'מכון', 'חדר כושר',
                'Place', 'studio', 'fitness', 'gym'
            ]
            has_activity_keyword = any(keyword in desc for keyword in activity_keywords)
            
            # IMPROVED DETECTION: Accept if it has price OR (location AND activity keyword)
            is_potential_activity = (
                (has_price and has_multiple_lines) or  # Has price and multi-line
                (has_location and has_activity_keyword and has_multiple_lines)  # Has location, activity keyword, and multi-line
            )
            
            if is_potential_activity:
                x, y = self.parse_bounds(elem['bounds'])
                if x > 0 and y > 0:  # Valid coordinates
                    
                    # CRITICAL: Check if activity's bottom edge is above map button
                    bounds = elem['bounds']
                    if bounds and '[' in bounds:
                        import re
                        coords = re.findall(r'\[(\d+),(\d+)\]', bounds)
                        if len(coords) >= 2:
                            x1, y1 = map(int, coords[0])  # Top-left
                            x2, y2 = map(int, coords[1])  # Bottom-right
                            
                            # Skip if activity's bottom edge touches or overlaps with map button
                            if y2 >= self.dangerous_map_button['top_y']:
                                activity_name = desc.split('\n')[0] if '\n' in desc else desc
                                print(f"⚠️ Skipping activity '{activity_name[:25]}...' - bottom Y={y2} >= map top Y={self.dangerous_map_button['top_y']}")
                                continue
                    
                    # Additional safety check for bottom navigation area
                    if y > 1900:  # Keep existing check as backup
                        continue
                    
                    # Check element size to avoid tiny buttons
                    bounds = elem['bounds']
                    if bounds and '[' in bounds:
                        import re
                        coords = re.findall(r'\[(\d+),(\d+)\]', bounds)
                        if len(coords) >= 2:
                            x1, y1 = map(int, coords[0])
                            x2, y2 = map(int, coords[1])
                            width = x2 - x1
                            height = y2 - y1
                            
                            # Skip very small elements (reduced threshold)
                            if width < 150 or height < 80:
                                continue
                    
                    activities.append({
                        'description': desc,
                        'x': x,
                        'y': y,
                        'bounds': elem['bounds'],
                        'detection_reason': 'price' if has_price else 'location+activity'
                    })
                    
                    activity_name = desc.split('\n')[0] if '\n' in desc else desc
                    reason = "(has price)" if has_price else "(location+keyword)"
                    print(f"✅ Found activity {reason}: {activity_name[:40]}... at ({x}, {y})")
        
        # Sort activities by Y coordinate (top to bottom) to process from top
        activities.sort(key=lambda a: a['y'])
        
        return activities
    
    def is_activity_fully_visible(self, activity: Dict, root: ET.Element) -> bool:
        """Check if an activity is fully visible on screen (not cut off at edges)"""
        try:
            # Get screen dimensions by finding the maximum coordinates in the UI
            screen_height = 2400  # Typical Android screen height
            screen_width = 1080   # Typical Android screen width
            
            # Parse activity bounds to get actual dimensions
            bounds = activity['bounds']
            if bounds and '[' in bounds:
                import re
                coords = re.findall(r'\[(\d+),(\d+)\]', bounds)
                if len(coords) >= 2:
                    x1, y1 = map(int, coords[0])
                    x2, y2 = map(int, coords[1])
                    
                    # Check if activity is fully visible (not cut off at screen edges)
                    # Leave some margin for UI elements (status bar, navigation bar)
                    margin_top = 100     # Status bar area
                    margin_bottom = 200  # Navigation bar area
                    margin_sides = 50    # Side margins
                    
                    # Activity is fully visible if:
                    # - Top edge is below status bar
                    # - Bottom edge is above navigation bar
                    # - Left and right edges are within screen bounds
                    is_fully_visible = (
                        y1 >= margin_top and                    # Not cut off at top
                        y2 <= screen_height - margin_bottom and # Not cut off at bottom
                        x1 >= margin_sides and                  # Not cut off at left
                        x2 <= screen_width - margin_sides       # Not cut off at right
                    )
                    
                    if not is_fully_visible:
                        activity_name = activity['description'].split('\n')[0] if '\n' in activity['description'] else activity['description']
                        print(f"   📏 Activity bounds check for {activity_name[:25]}...: [{x1},{y1}][{x2},{y2}] - {'✅ fully visible' if is_fully_visible else '❌ partially cut off'}")
                    
                    return is_fully_visible
            
            # If we can't parse bounds, assume it's visible
            return True
            
        except Exception as e:
            print(f"⚠️ Error checking activity visibility: {e}")
            # If we can't determine visibility, assume it's visible to avoid missing activities
            return True
    
    def get_current_selected_day(self, root: ET.Element) -> Optional[Dict]:
        """Find the currently selected day from the day selection bar"""
        clickable_elements = self.extract_clickable_elements(root)
        
        for elem in clickable_elements:
            desc = elem['desc']
            # Look for day patterns like "23\nשני" (number + day name)
            if '\n' in desc and len(desc.split('\n')) == 2:
                parts = desc.split('\n')
                if parts[0].strip().isdigit():
                    day_number = parts[0].strip()
                    day_name = parts[1].strip()
                    # Check if this seems like a Hebrew day name
                    hebrew_days = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת']
                    if day_name in hebrew_days:
                        x, y = self.parse_bounds(elem['bounds'])
                        return {
                            'day_number': day_number,
                            'day_name': day_name,
                            'x': x,
                            'y': y,
                            'bounds': elem['bounds']
                        }
        return None
    
    def get_available_days(self, root: ET.Element) -> List[Dict]:
        """Get all available days from the day selection bar"""
        clickable_elements = self.extract_clickable_elements(root)
        days = []
        
        for elem in clickable_elements:
            desc = elem['desc']
            # Look for day patterns like "23\nשני" (number + day name)
            if '\n' in desc and len(desc.split('\n')) == 2:
                parts = desc.split('\n')
                if parts[0].strip().isdigit():
                    day_number = parts[0].strip()
                    day_name = parts[1].strip()
                    # Check if this seems like a Hebrew day name
                    hebrew_days = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת']
                    if day_name in hebrew_days:
                        x, y = self.parse_bounds(elem['bounds'])
                        days.append({
                            'day_number': day_number,
                            'day_name': day_name,
                            'x': x,
                            'y': y,
                            'bounds': elem['bounds']
                        })
        
        # Sort by day number
        days.sort(key=lambda d: int(d['day_number']))
        return days
    
    def click_day(self, day: Dict) -> bool:
        """Click on a specific day in the day selection bar with verification"""
        print(f"📅 Switching to day {day['day_number']} ({day['day_name']}) at coordinates ({day['x']}, {day['y']})")
        
        # Use direct tap instead of smart waiting to avoid interference
        success, _ = self.run_adb_command(f"adb shell input tap {day['x']} {day['y']}")
        
        if success:
            print(f"✅ Tap successful for day {day['day_number']}")
            # Wait for the schedule to reload for the new day (fast day switching)
            self.wait_for_content_load("schedule", max_wait=2)
            return True
        else:
            print(f"❌ Tap failed for day {day['day_number']}")
            return False
    
    def extract_schedule_from_screen(self, root: ET.Element, activity_name: str, current_day: Dict = None) -> Dict:
        """Extract schedule information from activity detail screen for a specific day"""
        all_descriptions = self.extract_all_descriptions(root)
        
        result = {
            'activity_name': activity_name,
            'current_day': current_day,  # Include day information
            'calendar_dates': [],
            'activity_types': [],
            'instructors': [],
            'schedule_items': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # Extract calendar dates (day numbers with Hebrew day names)
        for desc in all_descriptions:
            if '\n' in desc and any(day in desc for day in ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת']):
                date_parts = desc.split('\n')
                if len(date_parts) == 2 and date_parts[0].strip().isdigit():
                    result['calendar_dates'].append({
                        'date': date_parts[0].strip(),
                        'day': date_parts[1].strip()
                    })
        
        # Extract activity types and instructors from single-line descriptions
        common_activity_types = ['כל סוגי הפעילות', 'אימון פונקציונלי', 'אימון תחנות', 'פילאטיס', 'FLOW', 'CLASSIC', 'Teen', 'יוגה']
        common_instructors = ['כל המדריכים']
        
        for desc in all_descriptions:
            # Skip multi-line descriptions for this section
            if '\n' in desc:
                continue
                
            if desc in common_activity_types:
                if desc not in result['activity_types']:
                    result['activity_types'].append(desc)
            elif desc in common_instructors or 'מדריכ' in desc:
                if desc not in result['instructors']:
                    result['instructors'].append(desc)
            # Check for instructor names (Hebrew names, typically 2-3 words)
            elif (len(desc.split()) <= 3 and 
                  any(char in desc for char in 'אבגדהוזחטיכלמנסעפצקרשת') and
                  desc not in common_activity_types and
                  desc not in ['האטה בזום', 'אשטנגה בסטודיו'] and  # Skip activity type variations
                  not desc.strip().isdigit()):
                if desc not in result['instructors']:
                    result['instructors'].append(desc)
        
        # Extract schedule items - FIXED LOGIC
        # Look for multi-line descriptions that contain time patterns
        for desc in all_descriptions:
            if '\n' in desc and ':' in desc and '-' in desc:
                lines = desc.split('\n')
                if len(lines) >= 2:
                    # Check if first line contains time pattern (HH:MM - HH:MM)
                    first_line = lines[0].strip()
                    if ':' in first_line and '-' in first_line:
                        # This looks like a schedule item!
                        schedule_item = {
                            'raw_description': desc,
                            'time': first_line,
                            'availability_status': '',
                            'spots_left': None,
                            'is_full': False,
                            'activity_type': '',
                            'instructor': '',
                            'additional_info': []
                        }
                        
                        # Process remaining lines
                        for i, line in enumerate(lines[1:], 1):
                            line_clean = line.strip()
                            if not line_clean:
                                continue
                            
                            # Extract availability information
                            if any(word in line_clean for word in ['מלא', 'מקום', 'נשאר', 'נשארו', 'זמין']):
                                schedule_item['availability_status'] = line_clean
                                
                                # Parse specific availability patterns
                                if 'כבר מלא' in line_clean or line_clean == 'מלא':
                                    schedule_item['is_full'] = True
                                    schedule_item['spots_left'] = 0
                                elif 'נשאר מקום אחד' in line_clean:
                                    schedule_item['spots_left'] = 1
                                elif 'נשארו' in line_clean and 'מקומות' in line_clean:
                                    # Extract number from "נשארו X מקומות"
                                    import re
                                    numbers = re.findall(r'\d+', line_clean)
                                    if numbers:
                                        schedule_item['spots_left'] = int(numbers[0])
                                elif 'מקום' in line_clean:
                                    schedule_item['spots_left'] = 'available'
                            
                            # Extract activity type (second line typically)
                            elif i == 1 or any(word in line_clean for word in ['בסטודיו', 'בזום', 'אימון', 'פילאטיס', 'יוגה', 'FLOW', 'CLASSIC', 'Teen']):
                                if not schedule_item['activity_type']:  # Take first match
                                    schedule_item['activity_type'] = line_clean
                            
                            # Extract instructor name (typically last line, Hebrew name)
                            elif (any(char in line_clean for char in 'אבגדהוזחטיכלמנסעפצקרשת') and
                                  len(line_clean.split()) <= 3 and
                                  not any(word in line_clean for word in ['מלא', 'מקום', 'בסטודיו', 'בזום'])):
                                if not schedule_item['instructor']:  # Take first match
                                    schedule_item['instructor'] = line_clean
                            
                            # Store any other information
                            else:
                                schedule_item['additional_info'].append(line_clean)
                        
                        # Set default availability if no specific info found
                        if not schedule_item['availability_status']:
                            schedule_item['availability_status'] = 'Available (no specific info)'
                            schedule_item['spots_left'] = 'unknown'
                        
                        # Always add if we have a time
                        if schedule_item['time']:
                            # Add day information to each schedule item
                            if current_day:
                                schedule_item['day_number'] = current_day['day_number']
                                schedule_item['day_name'] = current_day['day_name']
                            
                            result['schedule_items'].append(schedule_item)
                            day_info = f" (Day {current_day['day_number']} - {current_day['day_name']})" if current_day else ""
                            print(f"   📋 Found schedule item: {schedule_item['time']} - {schedule_item['activity_type']} - {schedule_item['instructor']}{day_info}")
        
        return result
    
    def verify_activity_detail_screen(self, root: ET.Element) -> bool:
        """Verify we're on an activity detail screen with schedule"""
        descriptions = self.extract_all_descriptions(root)
        clickable_elements = self.extract_clickable_elements(root)
        
        # Look for schedule indicators
        has_schedule_button = any('לוח פעילויות' in elem['desc'] for elem in clickable_elements)
        has_calendar = any(day in ' '.join(descriptions) for day in ['ראשון', 'שני', 'שלישי'])
        has_times = any(':' in desc and '-' in desc for desc in descriptions)
        
        return has_schedule_button or (has_calendar and has_times)
    
    def navigate_to_schedule(self, root: ET.Element) -> bool:
        """Navigate to schedule view if not already there"""
        clickable_elements = self.extract_clickable_elements(root)
        
        # Look for schedule button
        for elem in clickable_elements:
            if 'לוח פעילויות' in elem['desc']:
                x, y = self.parse_bounds(elem['bounds'])
                return self.tap_element(x, y, "Schedule button")
        
        # If no explicit schedule button, we might already be on schedule view
        return True
    
    def scroll_down(self) -> bool:
        """Balanced scroll method - not too fast, not too slow"""
        print("📜 Scrolling down (moderate increment)")
        
        # Use balanced scroll distance - faster than ultra-conservative but not too fast
        # This ensures we make good progress while not missing activities
        success, _ = self.run_adb_command("adb shell input swipe 540 1400 540 1000 400")
        
        # Smart waiting for scroll to complete and new content to load
        self.wait_for_content_load("activity_list", max_wait=8)
        return success
    
    def count_schedule_items_on_screen(self, root: ET.Element) -> int:
        """Count how many schedule items (time slots) are visible on current screen"""
        descriptions = self.extract_all_descriptions(root)
        schedule_items_count = 0
        
        for desc in descriptions:
            # Look for time patterns (HH:MM - HH:MM) in multi-line descriptions
            if '\n' in desc and ':' in desc and '-' in desc:
                lines = desc.split('\n')
                if len(lines) >= 2:
                    first_line = lines[0].strip()
                    # Check if first line contains time pattern
                    if ':' in first_line and '-' in first_line:
                        schedule_items_count += 1
        
        return schedule_items_count
    
    def scroll_schedule_to_bottom(self, day_key: str = None) -> bool:
        """Smart scroll - scroll if there are 3+ schedule items, but only once per day"""
        print("📜 Checking if scrolling is needed...")
        
        # Track which days we've already scrolled to prevent loops
        if not hasattr(self, '_scrolled_days'):
            self._scrolled_days = set()
        
        if day_key and day_key in self._scrolled_days:
            print(f"   ✅ Already scrolled for {day_key} - skipping scroll")
            return True
        
        # Check current screen first
        current_root = self.capture_screen_quick("scroll_check_initial")
        if current_root is None:
            print("   ⚠️ Failed to capture screen for scroll check")
            return False
        
        initial_items = self.count_schedule_items_on_screen(current_root)
        print(f"   📊 Found {initial_items} schedule items on current screen")
        
        # Changed threshold from 4 to 3 items
        if initial_items < 3:
            print(f"   ✅ Only {initial_items} items visible - no scrolling needed (content fits on screen)")
            if day_key:
                self._scrolled_days.add(day_key)
            return True
        
        print(f"   📜 {initial_items} items visible - performing single scroll to capture hidden content...")
        
        # Perform ONE scroll to get additional content, then stop
        print(f"   📜 Performing single scroll for more content...")
        
        # Use a moderate scroll distance for schedule screens
        success, _ = self.run_adb_command("adb shell input swipe 540 1400 540 900 400")
        
        if success:
            print(f"   ✅ Scroll completed successfully")
            # Wait for content to load
            time.sleep(1)
            
            # Check what we have after scrolling
            check_root = self.capture_screen_quick("scroll_check_after")
            if check_root is not None:
                items_after_scroll = self.count_schedule_items_on_screen(check_root)
                print(f"   📊 After scroll: {items_after_scroll} items visible")
            
            # Mark this day as scrolled to prevent future scrolling
            if day_key:
                self._scrolled_days.add(day_key)
                print(f"   📝 Marked {day_key} as scrolled")
            
            return True
        else:
            print(f"   ⚠️ Scroll failed")
            return False
    
    def is_on_activities_screen(self, root: ET.Element) -> bool:
        """Simple check if we're on activities screen (has activities or activity elements)"""
        descriptions = self.extract_all_descriptions(root)
        clickable_elements = self.extract_clickable_elements(root)
        
        # Simple check: do we see activities or activity-related elements?
        all_text = ' '.join(descriptions + [elem['desc'] for elem in clickable_elements])
        
        # Look for activity indicators
        activity_indicators = ['₪', 'תל אביב', 'רמת גן', 'פילאטיס', 'יוגה', 'אימון', 'סטודיו']
        has_activities = any(indicator in all_text for indicator in activity_indicators)
        
        return has_activities
    
    def return_to_activities_screen(self) -> bool:
        """Simple return to activities screen - just press back once"""
        print("⬅️ Returning to activities screen")
        return self.go_back()
    
    def process_single_activity(self, activity: Dict) -> Optional[Dict]:
        """Process a single activity and extract its schedule for all available days"""
        activity_name = activity['description'].split('\n')[0] if '\n' in activity['description'] else activity['description']
        print(f"\n🎯 Processing activity: {activity_name}")
        
        # Click on activity
        if not self.tap_element(activity['x'], activity['y'], activity_name):
            print(f"❌ Failed to tap on {activity_name}")
            return None
        
        # Verify we're on activity detail screen
        detail_root = self.capture_screen(f"activity_detail_{self.current_activity_index}")
        if detail_root is None:
            print(f"❌ Failed to capture activity detail screen for {activity_name}")
            return None
        
        if not self.verify_activity_detail_screen(detail_root):
            print(f"⚠️ Not on activity detail screen for {activity_name}")
            return None
        
        # Navigate to schedule if needed
        if not self.navigate_to_schedule(detail_root):
            print(f"⚠️ Failed to navigate to schedule for {activity_name}")
            return None
        
        # Wait smartly for schedule screen to load
        self.wait_for_content_load("schedule", max_wait=12)
        schedule_root = self.capture_screen(f"schedule_{self.current_activity_index}_initial")
        if schedule_root is None:
            print(f"❌ Failed to capture schedule screen for {activity_name}")
            return None
        
        # Get all available days
        available_days = self.get_available_days(schedule_root)
        print(f"📅 Found {len(available_days)} available days for {activity_name}")
        
        if not available_days:
            print(f"⚠️ No day selection found, extracting current day only")
            current_day = self.get_current_selected_day(schedule_root)
            schedule_data = self.extract_schedule_from_screen(schedule_root, activity_name, current_day)
            print(f"✅ Extracted schedule for {activity_name}: {len(schedule_data['schedule_items'])} items")
            return schedule_data
        
        # Initialize combined result structure
        combined_result = {
            'activity_name': activity_name,
            'total_days_processed': 0,
            'days_schedule': {},  # Will store schedule for each day
            'all_schedule_items': [],  # Combined items from all days
            'calendar_dates': [],
            'activity_types': [],
            'instructors': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # Track processed days to avoid duplicates
        processed_days = set()
        
        # Process each available day sequentially and accurately
        for i, day in enumerate(available_days):
            try:
                day_key = f"{day['day_number']}_{day['day_name']}"
                
                # Check if we already processed this day
                if day_key in processed_days:
                    print(f"⏭️ Skipping day {day['day_number']} ({day['day_name']}) - already processed")
                    continue
                
                print(f"\n📅 Processing day {i+1}/{len(available_days)}: {day['day_number']} ({day['day_name']})")
                
                # Always re-capture the screen to get fresh day buttons
                print(f"🔄 Re-capturing screen to ensure accurate day selection...")
                fresh_root = self.capture_screen(f"fresh_schedule_{self.current_activity_index}_before_day_{day['day_number']}")
                if fresh_root is None:
                    print(f"❌ Failed to re-capture screen before day {day['day_number']}")
                    continue
                
                # Get updated day buttons from fresh screen
                fresh_days = self.get_available_days(fresh_root)
                if not fresh_days:
                    print(f"❌ No days found on fresh screen for day {day['day_number']}")
                    continue
                
                # Find the exact day we want to click
                target_day = None
                for fresh_day in fresh_days:
                    if fresh_day['day_number'] == day['day_number'] and fresh_day['day_name'] == day['day_name']:
                        target_day = fresh_day
                        break
                
                if target_day is None:
                    print(f"❌ Could not find day {day['day_number']} ({day['day_name']}) in fresh screen")
                    continue
                
                print(f"🎯 Found target day: {target_day['day_number']} ({target_day['day_name']}) at ({target_day['x']}, {target_day['y']})")
                
                # Check if we're already on this day and haven't processed it yet
                current_selected = self.get_current_selected_day(fresh_root)
                if current_selected and current_selected['day_number'] == target_day['day_number']:
                    print(f"ℹ️ Already on day {target_day['day_number']}, extracting current content")
                else:
                    # Click on the specific day
                    print(f"👆 Clicking on day {target_day['day_number']} ({target_day['day_name']})")
                    if not self.click_day(target_day):
                        print(f"❌ Failed to click on day {target_day['day_number']}")
                        continue
                    
                    # Wait extra time for day transition
                    print(f"⏳ Waiting for day {target_day['day_number']} to load completely...")
                    time.sleep(2)  # Extra wait for day transition
                
                # Capture screen after ensuring we're on the correct day
                day_schedule_root = self.capture_screen(f"schedule_{self.current_activity_index}_day_{target_day['day_number']}")
                if day_schedule_root is None:
                    print(f"❌ Failed to capture screen for day {target_day['day_number']}")
                    continue
                
                # Check if this day has no events - skip scrolling and extraction if empty
                if self.has_no_events_for_day(day_schedule_root):
                    print(f"📭 No events found for day {target_day['day_number']} ({target_day['day_name']}) - skipping detailed extraction")
                    
                    # Create empty result for this day
                    day_schedule = {
                        'activity_name': activity_name,
                        'current_day': target_day,
                        'calendar_dates': [],
                        'activity_types': [],
                        'instructors': [],
                        'schedule_items': [],
                        'no_events': True,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Store day-specific schedule (empty)
                    day_storage_key = f"day_{target_day['day_number']}_{target_day['day_name']}"
                    combined_result['days_schedule'][day_storage_key] = day_schedule
                    
                    # Mark this day as processed
                    processed_days.add(day_key)
                    print(f"✅ Marked empty day {target_day['day_number']} ({target_day['day_name']}) as processed")
                    
                    combined_result['total_days_processed'] += 1
                    print(f"✅ Day {target_day['day_number']} ({target_day['day_name']}) completed: 0 schedule items (no events)")
                    print(f"📝 Processed days so far: {sorted(processed_days)}")
                    
                    # Small delay and continue to next day
                    time.sleep(0.5)
                    continue
                
                # Verify we're actually on the selected day
                verify_day = self.get_current_selected_day(day_schedule_root)
                if verify_day and verify_day['day_number'] != target_day['day_number']:
                    print(f"⚠️ Day mismatch! Expected {target_day['day_number']}, got {verify_day['day_number']}")
                    print(f"🔄 Retrying day selection...")
                    # Try clicking again
                    if not self.click_day(target_day):
                        print(f"❌ Second attempt failed for day {target_day['day_number']}")
                        continue
                    time.sleep(3)  # Longer wait for retry
                    day_schedule_root = self.capture_screen(f"schedule_{self.current_activity_index}_day_{target_day['day_number']}_retry")
                
                # Scroll down to capture all schedule hours that might be hidden
                print(f"📜 Scrolling to capture all hours for day {target_day['day_number']}...")
                self.scroll_schedule_to_bottom(day_key)
                
                # Capture screen again after scrolling to get all hours
                day_schedule_root_full = self.capture_screen(f"schedule_{self.current_activity_index}_day_{target_day['day_number']}_full")
                if day_schedule_root_full is None:
                    print(f"⚠️ Failed to capture full schedule after scrolling, using partial data")
                    day_schedule_root_full = day_schedule_root
                
                # Extract schedule for this specific day (now with all hours)
                day_schedule = self.extract_schedule_from_screen(day_schedule_root_full, activity_name, target_day)
                
                # Store day-specific schedule
                day_storage_key = f"day_{target_day['day_number']}_{target_day['day_name']}"
                combined_result['days_schedule'][day_storage_key] = day_schedule
                
                # Mark this day as processed
                processed_days.add(day_key)
                print(f"✅ Marked day {target_day['day_number']} ({target_day['day_name']}) as processed")
                
                # Add to combined list
                combined_result['all_schedule_items'].extend(day_schedule['schedule_items'])
                
                # Merge other data (avoiding duplicates)
                for date_info in day_schedule['calendar_dates']:
                    if date_info not in combined_result['calendar_dates']:
                        combined_result['calendar_dates'].append(date_info)
                
                for activity_type in day_schedule['activity_types']:
                    if activity_type not in combined_result['activity_types']:
                        combined_result['activity_types'].append(activity_type)
                
                for instructor in day_schedule['instructors']:
                    if instructor not in combined_result['instructors']:
                        combined_result['instructors'].append(instructor)
                
                combined_result['total_days_processed'] += 1
                
                schedule_count = len(day_schedule['schedule_items'])
                print(f"✅ Day {target_day['day_number']} ({target_day['day_name']}) completed: {schedule_count} schedule items")
                print(f"📝 Processed days so far: {sorted(processed_days)}")
                
                # Small delay between days to ensure UI stability
                time.sleep(1)
                
            except Exception as e:
                print(f"❌ Error processing day {day['day_number']}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        total_items = len(combined_result['all_schedule_items'])
        print(f"\n✅ Completed {activity_name}: {combined_result['total_days_processed']} days, {total_items} total schedule items")
        
        return combined_result
    
    def save_results(self):
        """Save results to JSON file (using same filename throughout extraction)"""
        # Set filename once and reuse it
        if self.output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_filename = f"maccabi_activities_{timestamp}.json"
            print(f"📁 Output file set to: {self.output_filename}")
        
        output = {
            'extraction_info': {
                'timestamp': datetime.now().isoformat(),
                'total_activities_processed': len(self.results),
                'failed_activities': len(self.failed_activities),
                'script_version': '1.0',
                'last_updated': datetime.now().isoformat()
            },
            'activities': self.results,
            'failed_activities': self.failed_activities
        }
        
        with open(self.output_filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        # Only show save message every 10 saves to avoid spam
        if len(self.results) % 10 == 0 or len(self.results) < 10:
            print(f"💾 Results updated in: {self.output_filename}")
        
        return self.output_filename
    
    def print_summary(self):
        """Print summary of extraction results"""
        total_runtime = time.time() - self.start_time if self.start_time else 0
        
        print(f"\n" + "="*60)
        print(f"📊 EXTRACTION SUMMARY")
        print(f"="*60)
        print(f"✅ Successfully processed: {len(self.results)} activities")
        print(f"❌ Failed to process: {len(self.failed_activities)} activities")
        print(f"📈 Total schedule items extracted: {sum(len(activity.get('all_schedule_items', activity.get('schedule_items', []))) for activity in self.results)}")
        print(f"⏱️ Total runtime: {total_runtime/60:.1f} minutes ({total_runtime:.1f} seconds)")
        
        if len(self.results) > 0:
            avg_time_per_activity = total_runtime / len(self.results)
            print(f"📊 Average time per activity: {avg_time_per_activity:.1f} seconds")
        
        if self.results:
            print(f"\n🏆 Successfully processed activities:")
            for activity in self.results:
                schedule_count = len(activity['schedule_items'])
                print(f"  • {activity['activity_name']} ({schedule_count} schedule items)")
        
        if self.failed_activities:
            print(f"\n❌ Failed activities:")
            for activity in self.failed_activities:
                print(f"  • {activity}")
    
    def run(self):
        """Main execution function"""
        print("🚀 Starting Maccabi Activity Scraper")
        print("="*50)
        
        # Initial screen capture to verify starting state
        root = self.capture_screen("initial_state")
        if root is None:
            print("❌ Failed to capture initial screen state")
            return
        
        # Simple check - just assume we're starting from the right screen
        print("✅ Starting from activities screen (assuming correct position)")
        
        # Start time already initialized in __init__, but update for actual run start
        self.start_time = time.time()
        
        # IMPROVED APPROACH: Start from top, select activities immediately when fully visible
        print("\n🔄 IMPROVED EXTRACTION - Starting from top, selecting activities immediately when fully visible...")
        
        scroll_attempts = 0
        max_scroll_attempts = 200
        consecutive_identical_screens = 0
        last_screen_content = None
        
        while scroll_attempts < max_scroll_attempts:
            print(f"\n📄 Screen scan {scroll_attempts + 1}")
            
            # Capture current screen
            current_root = self.capture_screen(f"screen_{scroll_attempts}")
            if current_root is None:
                print("❌ Failed to capture current screen")
                break
            
            # Find activities on current screen - they're already sorted by Y coordinate (top to bottom)
            screen_activities = self.find_activities_on_screen(current_root)
            print(f"🔍 Found {len(screen_activities)} activities on current screen (sorted top to bottom)")
            
            # Process activities immediately as we find them, starting from the top
            new_activities_processed = 0
            
            for i, activity in enumerate(screen_activities):
                activity_name = activity['description'].split('\n')[0] if '\n' in activity['description'] else activity['description']
                
                # Check if we've already processed this activity
                if (activity_name in self.processed_activities or 
                    activity_name in self.failed_activity_names):
                    print(f"⏭️ Skipping already processed: {activity_name[:30]}...")
                    continue
                
                # Check if activity is fully visible (not cut off at edges)
                is_fully_visible = self.is_activity_fully_visible(activity, current_root)
                if not is_fully_visible:
                    print(f"👁️ Activity partially visible, will catch it on next scroll: {activity_name[:30]}...")
                    continue
                
                # Update discovered activities (for coordinate tracking)
                self.update_activity_discovery([activity])
                
                print(f"\n🎯 Processing FULLY VISIBLE activity #{i+1}: {activity_name[:50]}...")
                print(f"📍 Activity coordinates: ({activity['x']}, {activity['y']})")
                
                try:
                    # Process the activity immediately
                    self.current_activity_index += 1
                    result = self.process_single_activity(activity)
                    
                    if result:
                        # Mark as processed AFTER successful extraction
                        self.mark_activity_processed(activity_name)
                        self.results.append(result)
                        print(f"✅ Successfully processed {activity_name}")
                        new_activities_processed += 1
                        # Save JSON after every successful extraction
                        self.save_results()
                    else:
                        # Mark as failed
                        self.mark_activity_failed(activity_name)
                        self.failed_activities.append(activity_name)
                        print(f"❌ Failed to process {activity_name}")
                        # Also save failed attempts
                        self.save_results()
                
                except Exception as e:
                    print(f"❌ Exception processing {activity_name}: {e}")
                    self.mark_activity_failed(activity_name)
                    self.failed_activities.append(activity_name)
                
                # Return to activities screen after each activity
                print(f"⬅️ Returning to activities list...")
                if not self.return_to_activities_screen():
                    print("❌ Failed to return to activities screen, stopping extraction")
                    return
                
                # Brief pause between activities
                time.sleep(1)
                
                # Progress tracking
                if len(self.results) % 10 == 0 and len(self.results) > 0:
                    elapsed_time = time.time() - self.start_time if self.start_time else 0
                    avg_time_per_activity = elapsed_time / len(self.results) if len(self.results) > 0 else 0
                    
                    print(f"\n📊 PROGRESS UPDATE: {len(self.results)} activities processed")
                    print(f"⏱️ Time elapsed: {elapsed_time/60:.1f} minutes")
                    print(f"📈 Average per activity: {avg_time_per_activity:.1f} seconds")
                    print(f"🔄 Saving intermediate results...")
                    self.save_results()
            
            # Show discovery and processing stats
            stats = self.get_discovery_stats()
            print(f"📊 Current stats: {stats['discovered']} discovered, {stats['processed']} processed, {stats['failed']} failed, {new_activities_processed} new this screen")
            
            # Check if we've reached the bottom by comparing screen content
            current_screen_content = self.get_screen_signature(current_root)
            
            if last_screen_content is not None and current_screen_content == last_screen_content:
                consecutive_identical_screens += 1
                print(f"🔄 Screen content unchanged (identical screen #{consecutive_identical_screens})")
                
                # If we see the same screen content 3 times in a row, we've likely reached the bottom
                if consecutive_identical_screens >= 3:
                    print("🎯 BOTTOM REACHED: Screen content hasn't changed for 3 consecutive scrolls")
                    
                    # Do one final check for bottom indicators
                    if self.is_at_bottom_of_list(current_root):
                        print("✅ Confirmed: Reached bottom of activities list")
                        break
                    else:
                        print("⚠️ Bottom indicators not found, continuing to scroll...")
                        consecutive_identical_screens = 0  # Reset and keep trying
            else:
                consecutive_identical_screens = 0
                if new_activities_processed > 0:
                    print(f"✅ Screen content changed - processed {new_activities_processed} new activities")
                else:
                    print(f"✅ Screen content changed - no new activities to process")
            
            last_screen_content = current_screen_content
            
            # Continue scrolling unless we've definitely reached the bottom
            if scroll_attempts < max_scroll_attempts - 1:
                if not self.scroll_down():
                    print("❌ Failed to scroll down")
                    break
                scroll_attempts += 1
            else:
                print("⚠️ Reached maximum scroll attempts - stopping extraction")
                break
        
        # Show final stats
        final_stats = self.get_discovery_stats()
        print(f"\n🎯 EXTRACTION COMPLETE: {final_stats['discovered']} discovered, {final_stats['processed']} processed, {final_stats['failed']} failed")
        
        # Save results and print summary
        self.save_results()
        self.print_summary()
        
        print(f"\n🎉 Extraction completed successfully!")

def main():
    """Main entry point"""
    try:
        scraper = MaccabiScraper()
        scraper.run()
    except KeyboardInterrupt:
        print("\n\n⚠️ Extraction interrupted by user")
        if hasattr(scraper, 'results') and scraper.results:
            print("💾 Saving partial results...")
            scraper.save_results()
            scraper.print_summary()
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
