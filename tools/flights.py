"""
Flight Status Tools for Orion
Flight tracking, PNR status, live location, schedules

Uses free APIs:
- AviationStack (500 req/month free)
- OpenSky Network (free, real-time)
- FlightAware (via scraping)
"""

import os
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from langchain_core.tools import tool

logger = logging.getLogger("Orion")

# API Keys (optional for enhanced features)
AVIATIONSTACK_KEY = os.getenv("AVIATIONSTACK_API_KEY", "")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")


@tool
def get_flight_status(flight_number: str, date: str = "") -> str:
    """
    Get live status of a flight by flight number.
    
    Args:
        flight_number: Flight number like "AI101", "6E123", "UK943"
        date: Date in DD-MM-YYYY format (optional, defaults to today)
    
    Returns:
        Flight status, departure/arrival times, delays, live position
    """
    try:
        # Clean flight number
        flight = flight_number.strip().upper().replace(" ", "")
        
        if len(flight) < 3:
            return "❌ Invalid flight number. Use format like AI101, 6E123, UK943"
        
        if not date:
            date = datetime.now().strftime("%d-%m-%Y")
        
        # Try multiple sources
        result = _get_flight_aviationstack(flight, date)
        if result:
            return result
        
        result = _get_flight_opensky(flight)
        if result:
            return result
        
        # Fallback - provide airline info
        return _get_flight_info_fallback(flight, date)
        
    except Exception as e:
        logger.error(f"Flight status error: {e}")
        return f"❌ Error getting flight status: {str(e)}"


def _get_flight_aviationstack(flight: str, date: str) -> Optional[str]:
    """Get flight status from AviationStack API"""
    if not AVIATIONSTACK_KEY:
        return None
    
    try:
        url = "http://api.aviationstack.com/v1/flights"
        params = {
            "access_key": AVIATIONSTACK_KEY,
            "flight_iata": flight
        }
        
        with httpx.Client(timeout=15) as client:
            response = client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                flights = data.get("data", [])
                
                if flights:
                    return _format_aviationstack_response(flights[0])
                    
    except Exception as e:
        logger.debug(f"AviationStack error: {e}")
    return None


def _format_aviationstack_response(flight: dict) -> str:
    """Format AviationStack response"""
    try:
        flight_num = flight.get("flight", {}).get("iata", "N/A")
        airline = flight.get("airline", {}).get("name", "N/A")
        status = flight.get("flight_status", "N/A")
        
        departure = flight.get("departure", {})
        dep_airport = departure.get("airport", "N/A")
        dep_iata = departure.get("iata", "")
        dep_scheduled = departure.get("scheduled", "")
        dep_actual = departure.get("actual", "")
        dep_delay = departure.get("delay", 0)
        dep_terminal = departure.get("terminal", "")
        dep_gate = departure.get("gate", "")
        
        arrival = flight.get("arrival", {})
        arr_airport = arrival.get("airport", "N/A")
        arr_iata = arrival.get("iata", "")
        arr_scheduled = arrival.get("scheduled", "")
        arr_estimated = arrival.get("estimated", "")
        arr_delay = arrival.get("delay", 0)
        arr_terminal = arrival.get("terminal", "")
        arr_gate = arrival.get("gate", "")
        
        # Format times
        def format_time(ts):
            if not ts:
                return "N/A"
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return dt.strftime("%I:%M %p")
            except:
                return ts
        
        status_emoji = {
            "scheduled": "📅",
            "active": "✈️",
            "landed": "🛬",
            "cancelled": "❌",
            "diverted": "⚠️",
            "delayed": "⏰"
        }.get(status.lower(), "❓")
        
        message = f"""✈️ **Flight Status: {flight_num}**

🏢 **Airline**: {airline}
📊 **Status**: {status_emoji} {status.title()}

🛫 **Departure**:
  📍 {dep_airport} ({dep_iata})
  🕐 Scheduled: {format_time(dep_scheduled)}
  🕐 Actual: {format_time(dep_actual) if dep_actual else "Not departed"}
  {"⚠️ Delayed: " + str(dep_delay) + " min" if dep_delay else "✅ On time"}
  🚪 Terminal: {dep_terminal or "N/A"} | Gate: {dep_gate or "N/A"}

🛬 **Arrival**:
  📍 {arr_airport} ({arr_iata})
  🕐 Scheduled: {format_time(arr_scheduled)}
  🕐 Estimated: {format_time(arr_estimated) if arr_estimated else "N/A"}
  {"⚠️ Delayed: " + str(arr_delay) + " min" if arr_delay else "✅ On time"}
  🚪 Terminal: {arr_terminal or "N/A"} | Gate: {arr_gate or "N/A"}
"""
        
        # Live position if available
        live = flight.get("live")
        if live:
            lat = live.get("latitude", "N/A")
            lon = live.get("longitude", "N/A")
            alt = live.get("altitude", "N/A")
            speed = live.get("speed_horizontal", "N/A")
            
            message += f"""
📍 **Live Position**:
  🌍 Coordinates: {lat}, {lon}
  ⬆️ Altitude: {alt} ft
  💨 Speed: {speed} km/h
"""
        
        return message
        
    except Exception as e:
        logger.error(f"Format error: {e}")
        return str(flight)


def _get_flight_opensky(flight: str) -> Optional[str]:
    """Get live flight position from OpenSky Network"""
    try:
        # OpenSky uses callsign, try to find matching aircraft
        url = "https://opensky-network.org/api/states/all"
        
        with httpx.Client(timeout=15) as client:
            response = client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                states = data.get("states", [])
                
                # Search for matching callsign
                for state in states:
                    callsign = (state[1] or "").strip().upper()
                    if flight.replace("-", "").replace(" ", "") in callsign:
                        return _format_opensky_state(state, flight)
                        
    except Exception as e:
        logger.debug(f"OpenSky error: {e}")
    return None


def _format_opensky_state(state: list, flight: str) -> str:
    """Format OpenSky state vector"""
    try:
        callsign = state[1].strip() if state[1] else flight
        origin_country = state[2] or "Unknown"
        longitude = state[5] or 0
        latitude = state[6] or 0
        altitude = state[7] or state[13] or 0  # Baro or geo altitude
        on_ground = state[8] or False
        velocity = state[9] or 0  # m/s
        heading = state[10] or 0
        
        # Convert units
        altitude_ft = int(altitude * 3.28084) if altitude else 0
        speed_kmh = int(velocity * 3.6) if velocity else 0
        speed_knots = int(velocity * 1.944) if velocity else 0
        
        status = "🛬 On Ground" if on_ground else "✈️ In Flight"
        
        # Direction
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        dir_idx = int((heading + 22.5) / 45) % 8
        direction = directions[dir_idx]
        
        message = f"""✈️ **Live Flight: {callsign}**

📊 **Status**: {status}
🌍 **Origin Country**: {origin_country}

📍 **Live Position**:
  🗺️ Coordinates: {latitude:.4f}, {longitude:.4f}
  ⬆️ Altitude: {altitude_ft:,} ft ({int(altitude):,} m)
  💨 Speed: {speed_kmh} km/h ({speed_knots} knots)
  🧭 Heading: {int(heading)}° ({direction})

🔗 Track on FlightRadar: https://www.flightradar24.com/{callsign}
"""
        return message
        
    except Exception as e:
        logger.error(f"Format error: {e}")
        return None


def _get_flight_info_fallback(flight: str, date: str) -> str:
    """Provide basic flight info when APIs fail"""
    
    # Extract airline code
    airline_code = ""
    for i, char in enumerate(flight):
        if char.isdigit():
            airline_code = flight[:i]
            break
    
    # Common Indian airlines
    AIRLINES = {
        "AI": ("Air India", "Air India"),
        "6E": ("IndiGo", "IndiGo"),
        "UK": ("Vistara", "Vistara"),
        "SG": ("SpiceJet", "SpiceJet"),
        "G8": ("Go First", "Go First (GoAir)"),
        "I5": ("AirAsia India", "AirAsia India"),
        "QP": ("Akasa Air", "Akasa Air"),
        "IX": ("Air India Express", "Air India Express"),
        "2T": ("Alliance Air", "Alliance Air"),
        "S5": ("Star Air", "Star Air"),
        "EK": ("Emirates", "Emirates"),
        "QR": ("Qatar Airways", "Qatar Airways"),
        "SQ": ("Singapore Airlines", "Singapore Airlines"),
        "BA": ("British Airways", "British Airways"),
        "LH": ("Lufthansa", "Lufthansa"),
        "EY": ("Etihad", "Etihad Airways"),
        "TK": ("Turkish Airlines", "Turkish Airlines"),
    }
    
    airline_info = AIRLINES.get(airline_code.upper(), (None, None))
    
    message = f"""✈️ **Flight: {flight}**

"""
    
    if airline_info[0]:
        message += f"🏢 **Airline**: {airline_info[1]}\n"
    
    message += f"""📅 **Date**: {date}

⚠️ **Live status not available**

🔗 **Check status on**:
• FlightRadar24: https://www.flightradar24.com/{flight}
• FlightAware: https://flightaware.com/live/flight/{flight}
• FlightStats: https://www.flightstats.com/v2/flight-tracker/{airline_code}/{flight.replace(airline_code, '')}

💡 **Tip**: Set AVIATIONSTACK_API_KEY for live status (free: 500 req/month)
"""
    
    return message


@tool
def get_flight_by_route(from_city: str, to_city: str, date: str = "") -> str:
    """
    Search flights between two cities.
    
    Args:
        from_city: Departure city or airport code (e.g., "Delhi", "DEL", "BOM")
        to_city: Arrival city or airport code
        date: Date in DD-MM-YYYY format (optional)
    
    Returns:
        List of flights on the route
    """
    try:
        if not date:
            date = datetime.now().strftime("%d-%m-%Y")
        
        # Get airport codes
        from_code = _get_airport_code(from_city)
        to_code = _get_airport_code(to_city)
        
        message = f"""✈️ **Flights: {from_city.title()} → {to_city.title()}**
📅 **Date**: {date}

🔍 **Search on**:
• Google Flights: https://www.google.com/flights?q=flights+from+{from_code}+to+{to_code}
• MakeMyTrip: https://www.makemytrip.com/flights/{from_code.lower()}-{to_code.lower()}/
• Skyscanner: https://www.skyscanner.co.in/transport/flights/{from_code.lower()}/{to_code.lower()}/

🏢 **Airlines on this route**:
"""
        
        # Common routes and airlines
        ROUTE_AIRLINES = {
            ("DEL", "BOM"): ["AI", "6E", "UK", "SG", "QP"],
            ("DEL", "BLR"): ["AI", "6E", "UK", "SG", "QP", "I5"],
            ("BOM", "BLR"): ["AI", "6E", "UK", "SG", "I5"],
            ("DEL", "HYD"): ["AI", "6E", "UK", "SG"],
            ("DEL", "CCU"): ["AI", "6E", "UK", "SG"],
            ("DEL", "MAA"): ["AI", "6E", "UK", "SG"],
        }
        
        # Find matching route
        route_key = (from_code.upper(), to_code.upper())
        reverse_key = (to_code.upper(), from_code.upper())
        
        airlines = ROUTE_AIRLINES.get(route_key) or ROUTE_AIRLINES.get(reverse_key) or ["AI", "6E", "UK", "SG"]
        
        AIRLINE_NAMES = {
            "AI": "Air India",
            "6E": "IndiGo",
            "UK": "Vistara",
            "SG": "SpiceJet",
            "QP": "Akasa Air",
            "I5": "AirAsia India"
        }
        
        for code in airlines:
            name = AIRLINE_NAMES.get(code, code)
            message += f"  • {name} ({code})\n"
        
        message += f"""
💡 **Tip**: Use `get_flight_status("AI101")` to track a specific flight
"""
        
        return message
        
    except Exception as e:
        logger.error(f"Route search error: {e}")
        return f"❌ Error: {str(e)}"


def _get_airport_code(city: str) -> str:
    """Get airport code from city name"""
    AIRPORTS = {
        "delhi": "DEL",
        "new delhi": "DEL",
        "mumbai": "BOM",
        "bombay": "BOM",
        "bangalore": "BLR",
        "bengaluru": "BLR",
        "chennai": "MAA",
        "madras": "MAA",
        "kolkata": "CCU",
        "calcutta": "CCU",
        "hyderabad": "HYD",
        "ahmedabad": "AMD",
        "pune": "PNQ",
        "jaipur": "JAI",
        "goa": "GOI",
        "kochi": "COK",
        "cochin": "COK",
        "lucknow": "LKO",
        "guwahati": "GAU",
        "chandigarh": "IXC",
        "patna": "PAT",
        "bhopal": "BHO",
        "indore": "IDR",
        "nagpur": "NAG",
        "varanasi": "VNS",
        "amritsar": "ATQ",
        "srinagar": "SXR",
        "trivandrum": "TRV",
        "thiruvananthapuram": "TRV",
        "coimbatore": "CJB",
        "vizag": "VTZ",
        "visakhapatnam": "VTZ",
        "mangalore": "IXE",
        "ranchi": "IXR",
        "bhubaneswar": "BBI",
        "raipur": "RPR",
        "surat": "STV",
        "vadodara": "BDQ",
        "rajkot": "RAJ",
        "dubai": "DXB",
        "singapore": "SIN",
        "bangkok": "BKK",
        "london": "LHR",
        "new york": "JFK",
        "doha": "DOH",
        "abu dhabi": "AUH",
    }
    
    city_lower = city.lower().strip()
    
    # Direct match
    if city_lower in AIRPORTS:
        return AIRPORTS[city_lower]
    
    # If already a code
    if len(city) == 3 and city.upper().isalpha():
        return city.upper()
    
    # Partial match
    for key, code in AIRPORTS.items():
        if city_lower in key:
            return code
    
    return city.upper()[:3]


@tool
def get_airport_info(airport: str) -> str:
    """
    Get information about an airport.
    
    Args:
        airport: Airport code (DEL, BOM) or city name (Delhi, Mumbai)
    
    Returns:
        Airport details, terminals, contact info
    """
    AIRPORT_INFO = {
        "DEL": {
            "name": "Indira Gandhi International Airport",
            "city": "New Delhi",
            "terminals": ["T1 (Domestic)", "T2 (Domestic/International)", "T3 (International)"],
            "airlines_t1": "IndiGo, SpiceJet, GoAir",
            "airlines_t3": "Air India, Vistara, International",
            "metro": "Airport Express Line (Orange)",
            "website": "www.newdelhiairport.in"
        },
        "BOM": {
            "name": "Chhatrapati Shivaji Maharaj International Airport",
            "city": "Mumbai",
            "terminals": ["T1 (Domestic)", "T2 (International/Domestic)"],
            "airlines_t1": "IndiGo, GoAir, SpiceJet",
            "airlines_t2": "Air India, Vistara, International",
            "metro": "Line 3 (Aqua) - Under Construction",
            "website": "www.csia.in"
        },
        "BLR": {
            "name": "Kempegowda International Airport",
            "city": "Bengaluru",
            "terminals": ["T1 (Domestic)", "T2 (International)"],
            "metro": "Purple Line Extension",
            "website": "www.bengaluruairport.com"
        },
        "HYD": {
            "name": "Rajiv Gandhi International Airport",
            "city": "Hyderabad",
            "terminals": ["Single Terminal (Domestic & International)"],
            "metro": "MMTS Rail",
            "website": "www.hyderabad.aero"
        },
        "MAA": {
            "name": "Chennai International Airport",
            "city": "Chennai",
            "terminals": ["T1 (Domestic)", "T4 (International)"],
            "metro": "Chennai Metro",
            "website": "www.chennaiairport.com"
        },
        "CCU": {
            "name": "Netaji Subhas Chandra Bose International Airport",
            "city": "Kolkata",
            "terminals": ["Integrated Terminal"],
            "metro": "Kolkata Metro Extension",
            "website": "www.calcuttaairport.com"
        }
    }
    
    # Get code from input
    code = _get_airport_code(airport)
    
    info = AIRPORT_INFO.get(code)
    
    if info:
        message = f"""🛫 **{info['name']}**
📍 **City**: {info['city']}
🏷️ **Code**: {code}

🏢 **Terminals**:
"""
        for t in info.get('terminals', []):
            message += f"  • {t}\n"
        
        if info.get('metro'):
            message += f"\n🚇 **Metro**: {info['metro']}\n"
        
        message += f"\n🌐 **Website**: {info.get('website', 'N/A')}\n"
        
        message += f"""
🔗 **Live Departures**: https://www.flightradar24.com/airport/{code.lower()}/departures
🔗 **Live Arrivals**: https://www.flightradar24.com/airport/{code.lower()}/arrivals
"""
        return message
    
    return f"""🛫 **Airport: {code}**

❓ Detailed info not available.

🔗 **Check on**:
• FlightRadar24: https://www.flightradar24.com/airport/{code.lower()}
• FlightAware: https://flightaware.com/live/airport/{code}
"""


@tool
def track_flight_live(flight_number: str) -> str:
    """
    Get real-time live tracking link for a flight.
    
    Args:
        flight_number: Flight number like AI101, 6E123
    
    Returns:
        Links to track flight live on map
    """
    flight = flight_number.strip().upper().replace(" ", "").replace("-", "")
    
    # Extract airline for better links
    airline_code = ""
    for i, char in enumerate(flight):
        if char.isdigit():
            airline_code = flight[:i]
            break
    
    return f"""✈️ **Track Flight: {flight}**

🗺️ **Live Tracking Links**:

🔴 **FlightRadar24** (Best for live map):
   https://www.flightradar24.com/{flight}

🔵 **FlightAware** (Detailed history):
   https://flightaware.com/live/flight/{flight}

🟢 **Flightstats**:
   https://www.flightstats.com/v2/flight-tracker/{airline_code}/{flight.replace(airline_code, '')}

📱 **Mobile Apps**:
• FlightRadar24 (iOS/Android)
• Flighty (iOS)
• FlightAware (iOS/Android)

💡 Click any link above to see real-time position on map!
"""
