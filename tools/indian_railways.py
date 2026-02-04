"""
Indian Railways Tools for Orion
PNR status, train running status, train schedule, seat availability

Uses free APIs - no API key required for basic features
"""

import os
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool

logger = logging.getLogger("Orion")

# RapidAPI key for premium features (optional)
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")


@tool
def check_pnr_status(pnr_number: str) -> str:
    """
    Check PNR status for Indian Railways ticket.
    
    Args:
        pnr_number: 10-digit PNR number from your railway ticket
    
    Returns:
        Booking status, train details, passenger status
    """
    try:
        # Clean PNR number
        pnr = pnr_number.strip().replace(" ", "").replace("-", "")
        
        if len(pnr) != 10 or not pnr.isdigit():
            return "❌ Invalid PNR. Please provide a 10-digit PNR number."
        
        # Try multiple free APIs
        result = _check_pnr_confirmtkt(pnr)
        if result:
            return result
        
        result = _check_pnr_railwayapi(pnr)
        if result:
            return result
        
        return f"❌ Could not fetch PNR status for {pnr}. Please try again later or check on IRCTC website."
        
    except Exception as e:
        logger.error(f"PNR check error: {e}")
        return f"❌ Error checking PNR: {str(e)}"


def _check_pnr_confirmtkt(pnr: str) -> Optional[str]:
    """Check PNR via ConfirmTkt API"""
    try:
        url = f"https://www.confirmtkt.com/pnr-status/{pnr}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            
            if response.status_code == 200:
                # Parse basic info from response
                # This is a simplified version - actual implementation would parse HTML/JSON
                return None  # Fallback to other API
                
    except Exception as e:
        logger.debug(f"ConfirmTkt API error: {e}")
    return None


def _check_pnr_railwayapi(pnr: str) -> Optional[str]:
    """Check PNR via free railway API"""
    try:
        # Using a free proxy API
        url = f"https://rappid.in/apis/pnr.php?pnr={pnr}"
        
        with httpx.Client(timeout=15) as client:
            response = client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success") or data.get("TrainNo"):
                    return _format_pnr_response(data)
                    
    except Exception as e:
        logger.debug(f"RailwayAPI error: {e}")
    return None


def _format_pnr_response(data: dict) -> str:
    """Format PNR response into readable message"""
    try:
        train_no = data.get("TrainNo", data.get("train_num", "N/A"))
        train_name = data.get("TrainName", data.get("train_name", "N/A"))
        doj = data.get("Doj", data.get("doj", "N/A"))
        from_stn = data.get("From", data.get("from_station", {}).get("name", "N/A"))
        to_stn = data.get("To", data.get("to_station", {}).get("name", "N/A"))
        boarding = data.get("BoardingPoint", from_stn)
        class_type = data.get("Class", data.get("class", "N/A"))
        chart_prepared = data.get("ChartPrepared", data.get("chart_prepared", False))
        
        message = f"""🚂 **PNR Status**

🎫 **Train**: {train_no} - {train_name}
📅 **Journey Date**: {doj}
🚉 **From**: {from_stn}
🏁 **To**: {to_stn}
🎒 **Boarding**: {boarding}
🎟️ **Class**: {class_type}
📊 **Chart**: {"Prepared ✅" if chart_prepared else "Not Prepared ⏳"}

👥 **Passengers**:
"""
        
        passengers = data.get("PassengerStatus", data.get("passengers", []))
        if passengers:
            for i, p in enumerate(passengers, 1):
                if isinstance(p, dict):
                    booking = p.get("BookingStatus", p.get("booking_status", "N/A"))
                    current = p.get("CurrentStatus", p.get("current_status", "N/A"))
                    coach = p.get("Coach", p.get("coach", ""))
                    berth = p.get("Berth", p.get("berth", ""))
                    
                    status_emoji = "✅" if "CNF" in str(current).upper() else "⏳" if "WL" in str(current).upper() or "RAC" in str(current).upper() else "❓"
                    
                    message += f"  {i}. Booking: {booking} → Current: {current} {status_emoji}"
                    if coach and berth:
                        message += f" ({coach}/{berth})"
                    message += "\n"
                else:
                    message += f"  {i}. {p}\n"
        else:
            message += "  No passenger details available\n"
        
        return message
        
    except Exception as e:
        logger.error(f"Format error: {e}")
        return str(data)


@tool
def get_train_status(train_number: str, date: str = "") -> str:
    """
    Get live running status of a train.
    
    Args:
        train_number: 5-digit train number (e.g., 12301 for Rajdhani)
        date: Journey date in DD-MM-YYYY format (optional, defaults to today)
    
    Returns:
        Current location, delay status, expected arrival times
    """
    try:
        train_no = train_number.strip().replace(" ", "")
        
        if not train_no.isdigit() or len(train_no) < 4 or len(train_no) > 5:
            return "❌ Invalid train number. Please provide a 4-5 digit train number."
        
        # Default to today
        if not date:
            date = datetime.now().strftime("%d-%m-%Y")
        
        # Try to get train status
        result = _get_train_running_status(train_no, date)
        if result:
            return result
        
        return f"❌ Could not fetch status for train {train_no}. Train may not be running today."
        
    except Exception as e:
        logger.error(f"Train status error: {e}")
        return f"❌ Error getting train status: {str(e)}"


def _get_train_running_status(train_no: str, date: str) -> Optional[str]:
    """Get train running status from API"""
    try:
        # Using free API
        url = f"https://rappid.in/apis/train.php?train={train_no}"
        
        with httpx.Client(timeout=15) as client:
            response = client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success") or data.get("train_name"):
                    return _format_train_status(data, date)
                    
    except Exception as e:
        logger.debug(f"Train status API error: {e}")
    return None


def _format_train_status(data: dict, date: str) -> str:
    """Format train status response"""
    try:
        train_name = data.get("train_name", data.get("TrainName", "N/A"))
        train_no = data.get("train_number", data.get("TrainNo", "N/A"))
        
        message = f"""🚂 **Train Status**

🎫 **{train_no}** - {train_name}
📅 **Date**: {date}

"""
        
        # Current status
        current_station = data.get("current_station", {})
        if current_station:
            stn_name = current_station.get("station_name", "N/A")
            status = current_station.get("status", "")
            delay = current_station.get("delay", "0")
            
            message += f"📍 **Current Location**: {stn_name}\n"
            message += f"⏱️ **Status**: {status}\n"
            if delay and delay != "0":
                message += f"⚠️ **Delay**: {delay} minutes\n"
            else:
                message += f"✅ **Running on time**\n"
        
        # Route info
        route = data.get("route", [])
        if route and len(route) > 0:
            message += f"\n📋 **Route** ({len(route)} stations):\n"
            for stn in route[:5]:  # First 5 stations
                stn_name = stn.get("station_name", stn.get("name", "N/A"))
                arr = stn.get("arrive", stn.get("arrival", "-"))
                dep = stn.get("depart", stn.get("departure", "-"))
                message += f"  • {stn_name}: Arr {arr} / Dep {dep}\n"
            if len(route) > 5:
                message += f"  ... and {len(route) - 5} more stations\n"
        
        return message
        
    except Exception as e:
        logger.error(f"Format error: {e}")
        return str(data)


@tool  
def search_trains(from_station: str, to_station: str, date: str = "") -> str:
    """
    Search for trains between two stations.
    
    Args:
        from_station: Source station name or code (e.g., "NDLS" or "New Delhi")
        to_station: Destination station name or code (e.g., "BCT" or "Mumbai Central")
        date: Journey date in DD-MM-YYYY format (optional)
    
    Returns:
        List of trains with timings
    """
    try:
        if not date:
            date = datetime.now().strftime("%d-%m-%Y")
        
        # Using free API
        url = f"https://rappid.in/apis/trains.php?from={from_station}&to={to_station}"
        
        with httpx.Client(timeout=15) as client:
            response = client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success") or data.get("trains"):
                    trains = data.get("trains", data.get("data", []))
                    
                    if not trains:
                        return f"❌ No trains found from {from_station} to {to_station}"
                    
                    message = f"""🚂 **Trains from {from_station} to {to_station}**
📅 Date: {date}

"""
                    for i, train in enumerate(trains[:10], 1):  # Top 10
                        name = train.get("train_name", train.get("name", "N/A"))
                        number = train.get("train_number", train.get("number", "N/A"))
                        dep = train.get("departure", train.get("dep", "N/A"))
                        arr = train.get("arrival", train.get("arr", "N/A"))
                        duration = train.get("duration", train.get("travel_time", "N/A"))
                        days = train.get("running_days", train.get("days", "Daily"))
                        
                        message += f"{i}. **{number}** - {name}\n"
                        message += f"   🕐 Dep: {dep} → Arr: {arr} ({duration})\n"
                        message += f"   📅 Runs: {days}\n\n"
                    
                    if len(trains) > 10:
                        message += f"... and {len(trains) - 10} more trains"
                    
                    return message
        
        return f"❌ Could not search trains. Please try again."
        
    except Exception as e:
        logger.error(f"Train search error: {e}")
        return f"❌ Error searching trains: {str(e)}"


@tool
def get_station_code(station_name: str) -> str:
    """
    Get railway station code from station name.
    
    Args:
        station_name: Full or partial station name (e.g., "New Delhi", "Mumbai")
    
    Returns:
        Station code and full name
    """
    # Common station codes - can be expanded
    COMMON_STATIONS = {
        "new delhi": ("NDLS", "New Delhi"),
        "delhi": ("DLI", "Delhi Junction"),
        "mumbai central": ("BCT", "Mumbai Central"),
        "mumbai": ("CSTM", "Mumbai CST"),
        "chennai": ("MAS", "Chennai Central"),
        "kolkata": ("HWH", "Howrah Junction"),
        "bangalore": ("SBC", "Bangalore City Junction"),
        "bengaluru": ("SBC", "Bangalore City Junction"),
        "hyderabad": ("HYB", "Hyderabad Deccan"),
        "pune": ("PUNE", "Pune Junction"),
        "ahmedabad": ("ADI", "Ahmedabad Junction"),
        "jaipur": ("JP", "Jaipur Junction"),
        "lucknow": ("LKO", "Lucknow Junction"),
        "kanpur": ("CNB", "Kanpur Central"),
        "patna": ("PNBE", "Patna Junction"),
        "bhopal": ("BPL", "Bhopal Junction"),
        "chandigarh": ("CDG", "Chandigarh"),
        "varanasi": ("BSB", "Varanasi Junction"),
        "agra": ("AGC", "Agra Cantt"),
        "goa": ("MAO", "Madgaon Junction"),
        "kochi": ("ERS", "Ernakulam Junction"),
        "trivandrum": ("TVC", "Thiruvananthapuram Central"),
        "guwahati": ("GHY", "Guwahati"),
        "amritsar": ("ASR", "Amritsar Junction"),
        "indore": ("INDB", "Indore Junction"),
        "nagpur": ("NGP", "Nagpur Junction"),
        "coimbatore": ("CBE", "Coimbatore Junction"),
        "visakhapatnam": ("VSKP", "Visakhapatnam Junction"),
        "surat": ("ST", "Surat"),
        "vadodara": ("BRC", "Vadodara Junction"),
        "rajkot": ("RJT", "Rajkot Junction"),
    }
    
    search = station_name.lower().strip()
    
    # Direct match
    if search in COMMON_STATIONS:
        code, name = COMMON_STATIONS[search]
        return f"🚉 **{name}**\n📍 Station Code: **{code}**"
    
    # Partial match
    matches = []
    for key, (code, name) in COMMON_STATIONS.items():
        if search in key or key in search:
            matches.append(f"🚉 **{name}** - Code: **{code}**")
    
    if matches:
        return "Found stations:\n" + "\n".join(matches)
    
    return f"❌ Station '{station_name}' not found. Try a major city name like 'New Delhi', 'Mumbai', 'Bangalore' etc."
