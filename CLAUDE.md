# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Maccabi activity scraper project that automates the extraction of activity schedules from the Maccabi Move Android app using UI automation. The project uses Python and ADB (Android Debug Bridge) to navigate the app and extract structured data.

## Architecture

- **main.py**: Activity filtering script that processes extracted JSON data by date and time ranges
- **json_to_csv.py**: Data conversion utility that transforms JSON output to CSV format with proper schema
- **scraper/maccabi_activity_scraper.py**: Core scraper engine that handles UI automation, screen capture, and data extraction

The scraper follows a multi-phase approach:
1. Screen capture and UI hierarchy parsing using `uiautomator dump`
2. Activity detection with safety mechanisms (map button protection)
3. Day-by-day schedule extraction with scroll handling
4. JSON output with comprehensive metadata

## Development Commands

**Run the main activity filter:**
```bash
python3 main.py
```

**Convert JSON output to CSV:**
```bash
python3 json_to_csv.py
```

**Run the scraper (requires Android emulator):**
```bash
python3 scraper/maccabi_activity_scraper.py
```

**Test ADB connection:**
```bash
adb devices
adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'
```

## Key Implementation Details

### Safety Mechanisms
- Map button protection system prevents accidental navigation away from activities list
- Coordinate-based element filtering ensures clicks are safe
- Retry logic with adaptive waiting for UI transitions

### Data Extraction Strategy  
- Multi-day processing: extracts schedules for all available days per activity
- Smart scrolling: detects when scrolling is needed and prevents infinite loops
- Duplicate prevention: tracks processed activities to avoid reprocessing

### Output Format
- Primary output: timestamped JSON files (`maccabi_activities_YYYYMMDD_HHMMSS.json`)
- Includes extraction metadata, activity details, and schedule items
- CSV conversion maintains schema compatibility with downstream systems

## Dependencies

The project requires:
- Python 3.6+
- Android emulator with Maccabi app installed and logged in
- ADB configured and accessible in PATH
- pandas (for CSV conversion)

## Testing Approach

No formal test framework is used. Testing is done through:
- Manual verification of JSON output structure
- Comparison of extracted data against app UI
- CSV output validation for schema compliance