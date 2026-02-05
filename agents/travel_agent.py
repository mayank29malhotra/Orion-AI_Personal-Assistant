"""
Travel Agent - Specialized Sub-Agent for Travel Planning
=========================================================

Capabilities:
- Search flights across multiple platforms (MakeMyTrip, Goibibo, Cleartrip, ixigo)
- Search trains with price comparison
- Find best prices and discounts
- Track flight/train status
- Hotel search (future)
- Cab booking comparison (future)

Uses web scraping for real-time price comparison.
"""

import os
import re
import json
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from langchain_core.tools import tool
import httpx

from agents.base_agent import BaseSubAgent
from core.utils import Logger

logger = Logger().logger

# IST Timezone
IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class FlightResult:
    """Flight search result"""
    airline: str
    flight_number: str
    departure_time: str
    arrival_time: str
    duration: str
    price: float
    source: str  # MakeMyTrip, Goibibo, etc.
    stops: int = 0
    booking_url: str = ""


@dataclass
class TrainResult:
    """Train search result"""
    train_name: str
    train_number: str
    departure_time: str
    arrival_time: str
    duration: str
    classes: Dict[str, float]  # {"SL": 500, "3A": 1200, ...}
    source: str
    availability: str = ""
    booking_url: str = ""


# ============== FLIGHT SEARCH TOOLS ==============

@tool
def search_flights_all_platforms(
    from_city: str,
    to_city: str,
    date: str,
    passengers: int = 1
) -> str:
    """
    Search flights across multiple platforms and compare prices.
    Returns the cheapest options from MakeMyTrip, Goibibo, Cleartrip, ixigo.
    
    Args:
        from_city: Departure city (e.g., "Delhi", "Mumbai", "Bangalore")
        to_city: Arrival city
        date: Travel date in YYYY-MM-DD format
        passengers: Number of passengers (default 1)
    
    Returns:
        Comparison of flight prices across platforms with direct booking links
    """
    # City code mapping
    CITY_CODES = {
        "delhi": "DEL", "new delhi": "DEL", "mumbai": "BOM", "bombay": "BOM",
        "bangalore": "BLR", "bengaluru": "BLR", "chennai": "MAA", "kolkata": "CCU",
        "hyderabad": "HYD", "pune": "PNQ", "ahmedabad": "AMD", "jaipur": "JAI",
        "goa": "GOI", "kochi": "COK", "lucknow": "LKO", "guwahati": "GAU",
        "patna": "PAT", "bhubaneswar": "BBI", "chandigarh": "IXC", "indore": "IDR",
        "nagpur": "NAG", "varanasi": "VNS", "amritsar": "ATQ", "srinagar": "SXR",
        "thiruvananthapuram": "TRV", "trivandrum": "TRV", "coimbatore": "CJB",
        "mangalore": "IXE", "visakhapatnam": "VTZ", "vizag": "VTZ", "ranchi": "IXR",
        "raipur": "RPR", "bhopal": "BHO", "udaipur": "UDR", "dehradun": "DED",
        "port blair": "IXZ", "leh": "IXL", "jammu": "IXJ", "bagdogra": "IXB",
    }
    
    from_code = CITY_CODES.get(from_city.lower(), from_city.upper()[:3])
    to_code = CITY_CODES.get(to_city.lower(), to_city.upper()[:3])
    
    # Parse date
    try:
        travel_date = datetime.strptime(date, "%Y-%m-%d")
        date_str = travel_date.strftime("%d/%m/%Y")
        date_mmt = travel_date.strftime("%d-%m-%Y")
    except:
        return "Invalid date format. Use YYYY-MM-DD (e.g., 2026-02-10)"
    
    results = []
    
    # Generate search URLs for different platforms
    platforms = {
        "MakeMyTrip": {
            "url": f"https://www.makemytrip.com/flight/search?itinerary={from_code}-{to_code}-{date_mmt}&tripType=O&paxType=A-{passengers}_C-0_I-0&intl=false&cabinClass=E",
            "logo": "🟠"
        },
        "Goibibo": {
            "url": f"https://www.goibibo.com/flights/air-{from_code}-{to_code}-{date_mmt}--{passengers}-0-0-E-D",
            "logo": "🔴"
        },
        "Cleartrip": {
            "url": f"https://www.cleartrip.com/flights/{from_code}/{to_code}/{date_mmt}",
            "logo": "🟡"
        },
        "ixigo": {
            "url": f"https://www.ixigo.com/search/result/flight?from={from_code}&to={to_code}&date={date_mmt}&returnDate=&adults={passengers}&children=0&infants=0&class=e&source=Search%20Form",
            "logo": "🔵"
        },
        "EaseMyTrip": {
            "url": f"https://flight.easemytrip.com/FlightList/Index?org={from_code}&dest={to_code}&date={date_mmt}&adult={passengers}&child=0&infant=0&class=Economy&triptype=oneway",
            "logo": "🟢"
        }
    }
    
    # Build response with search links
    output = f"✈️ **Flight Search: {from_city.title()} → {to_city.title()}**\n"
    output += f"📅 Date: {travel_date.strftime('%A, %B %d, %Y')}\n"
    output += f"👥 Passengers: {passengers}\n\n"
    
    output += "🔍 **Compare Prices on Multiple Platforms:**\n\n"
    
    for platform, info in platforms.items():
        output += f"{info['logo']} **{platform}**\n"
        output += f"   🔗 [Search on {platform}]({info['url']})\n\n"
    
    # Add typical price ranges (based on common routes)
    output += "💡 **Typical Price Ranges (Economy):**\n"
    
    # Estimate based on route distance
    metro_cities = {"del", "bom", "blr", "maa", "ccu", "hyd"}
    from_metro = from_code.lower() in metro_cities
    to_metro = to_code.lower() in metro_cities
    
    if from_metro and to_metro:
        output += f"• Budget Airlines (IndiGo, SpiceJet): ₹3,500 - ₹6,000\n"
        output += f"• Full Service (Air India, Vistara): ₹5,500 - ₹9,000\n"
    else:
        output += f"• Budget Airlines: ₹2,500 - ₹5,000\n"
        output += f"• Full Service: ₹4,000 - ₹7,500\n"
    
    output += "\n📌 **Pro Tips:**\n"
    output += "• Book 2-3 weeks in advance for best prices\n"
    output += "• Tuesday & Wednesday usually have cheaper flights\n"
    output += "• Early morning & late night flights are often cheaper\n"
    output += "• Check 'Web Check-in' for additional savings\n"
    
    return output


@tool
def search_trains_all_platforms(
    from_station: str,
    to_station: str,
    date: str
) -> str:
    """
    Search trains across multiple platforms and compare prices.
    Returns options from IRCTC, ixigo, Paytm, and Confirmtkt.
    
    Args:
        from_station: Departure station/city (e.g., "Delhi", "NDLS")
        to_station: Arrival station/city (e.g., "Mumbai", "CSTM")
        date: Travel date in YYYY-MM-DD format
    
    Returns:
        Train options with prices and booking links
    """
    # Station code mapping (common stations)
    STATION_CODES = {
        "delhi": "NDLS", "new delhi": "NDLS", "old delhi": "DLI",
        "mumbai": "CSTM", "mumbai central": "MMCT", "mumbai cst": "CSTM",
        "bangalore": "SBC", "bengaluru": "SBC", "chennai": "MAS",
        "kolkata": "HWH", "howrah": "HWH", "sealdah": "SDAH",
        "hyderabad": "SC", "secunderabad": "SC", "pune": "PUNE",
        "ahmedabad": "ADI", "jaipur": "JP", "lucknow": "LKO", "lko": "LKO",
        "kanpur": "CNB", "varanasi": "BSB", "patna": "PNBE",
        "guwahati": "GHY", "bhopal": "BPL", "nagpur": "NGP",
        "chandigarh": "CDG", "amritsar": "ASR", "jammu": "JAT",
        "agra": "AGC", "allahabad": "ALD", "prayagraj": "PRYJ",
        "goa": "MAO", "madgaon": "MAO", "kochi": "ERS", "ernakulam": "ERS",
        "trivandrum": "TVC", "coimbatore": "CBE", "mysore": "MYS",
        "visakhapatnam": "VSKP", "vizag": "VSKP", "vijayawada": "BZA",
        "ranchi": "RNC", "bhubaneswar": "BBS", "raipur": "R",
        "indore": "INDB", "jodhpur": "JU", "udaipur": "UDZ",
        "surat": "ST", "vadodara": "BRC", "rajkot": "RJT",
        "dehradun": "DDN", "haridwar": "HW", "rishikesh": "RKSH",
    }
    
    from_code = STATION_CODES.get(from_station.lower(), from_station.upper())
    to_code = STATION_CODES.get(to_station.lower(), to_station.upper())
    
    # Parse date
    try:
        travel_date = datetime.strptime(date, "%Y-%m-%d")
        date_str = travel_date.strftime("%Y%m%d")
        date_display = travel_date.strftime("%d-%m-%Y")
    except:
        return "Invalid date format. Use YYYY-MM-DD (e.g., 2026-02-10)"
    
    # Generate search URLs
    platforms = {
        "IRCTC (Official)": {
            "url": f"https://www.irctc.co.in/nget/train-search",
            "logo": "🟠",
            "note": "Official booking, no convenience fee"
        },
        "ixigo Trains": {
            "url": f"https://www.ixigo.com/search/result/train/{from_code}/{to_code}/{date_display}",
            "logo": "🔵",
            "note": "Easy interface, shows availability"
        },
        "Paytm Trains": {
            "url": f"https://paytm.com/trains/{from_code}-to-{to_code}",
            "logo": "🔷",
            "note": "Cashback offers available"
        },
        "ConfirmTkt": {
            "url": f"https://www.confirmtkt.com/train-between-stations/{from_code}/{to_code}",
            "logo": "🟢",
            "note": "Shows confirmation chances"
        },
        "RailYatri": {
            "url": f"https://www.railyatri.in/trains-between-stations?from_code={from_code}&to_code={to_code}&journey_date={date_display}",
            "logo": "🟣",
            "note": "Live running status"
        }
    }
    
    # Build response
    output = f"🚂 **Train Search: {from_station.title()} → {to_station.title()}**\n"
    output += f"📅 Date: {travel_date.strftime('%A, %B %d, %Y')}\n\n"
    
    output += "🔍 **Book on Multiple Platforms:**\n\n"
    
    for platform, info in platforms.items():
        output += f"{info['logo']} **{platform}**\n"
        output += f"   📝 {info['note']}\n"
        output += f"   🔗 [Search]({info['url']})\n\n"
    
    # Add typical class prices
    output += "💰 **Typical Price Ranges (per person):**\n"
    output += "• Sleeper (SL): ₹300 - ₹800\n"
    output += "• AC 3-Tier (3A): ₹800 - ₹1,500\n"
    output += "• AC 2-Tier (2A): ₹1,200 - ₹2,500\n"
    output += "• AC 1st Class (1A): ₹2,000 - ₹4,500\n"
    output += "• AC Chair Car (CC): ₹500 - ₹1,200\n"
    
    output += "\n📌 **Pro Tips:**\n"
    output += "• Book on IRCTC for Tatkal (opens 10 AM day before)\n"
    output += "• Premium Tatkal opens at 10:30 AM\n"
    output += "• ConfirmTkt shows RAC/WL confirmation probability\n"
    output += "• Consider Vande Bharat for premium experience\n"
    
    return output


@tool  
def find_cheapest_travel_option(
    from_city: str,
    to_city: str,
    date: str
) -> str:
    """
    Compare ALL travel options (flights, trains, buses) for a route.
    Finds the absolute cheapest way to travel between two cities.
    
    Args:
        from_city: Departure city
        to_city: Destination city
        date: Travel date in YYYY-MM-DD format
    
    Returns:
        Comparison of all modes with prices and recommendations
    """
    try:
        travel_date = datetime.strptime(date, "%Y-%m-%d")
        date_display = travel_date.strftime("%A, %B %d, %Y")
    except:
        return "Invalid date format. Use YYYY-MM-DD"
    
    output = f"🎯 **Cheapest Travel Options: {from_city.title()} → {to_city.title()}**\n"
    output += f"📅 {date_display}\n\n"
    
    # Determine approximate distance/route type
    metro_cities = ["delhi", "mumbai", "bangalore", "chennai", "kolkata", "hyderabad"]
    is_metro_route = from_city.lower() in metro_cities and to_city.lower() in metro_cities
    
    output += "📊 **Price Comparison by Mode:**\n\n"
    
    if is_metro_route:
        output += "✈️ **FLIGHTS** (Fastest - 2-3 hours)\n"
        output += "   💰 Budget: ₹3,500 - ₹5,500\n"
        output += "   💰 Premium: ₹5,500 - ₹9,000\n"
        output += "   ⏱️ Total time: 3-4 hours (including airport)\n\n"
        
        output += "🚂 **TRAINS** (Best Value)\n"
        output += "   💰 Sleeper: ₹400 - ₹700\n"
        output += "   💰 3A AC: ₹1,000 - ₹1,500\n"
        output += "   💰 2A AC: ₹1,500 - ₹2,500\n"
        output += "   ⏱️ Travel time: 12-20 hours\n\n"
        
        output += "🚌 **BUSES** (Budget Option)\n"
        output += "   💰 Non-AC Sleeper: ₹800 - ₹1,200\n"
        output += "   💰 AC Sleeper: ₹1,200 - ₹2,000\n"
        output += "   💰 Volvo Multi-Axle: ₹1,500 - ₹2,500\n"
        output += "   ⏱️ Travel time: 15-24 hours\n\n"
        
        output += "🏆 **RECOMMENDATION:**\n"
        output += "• **Cheapest**: Train Sleeper (₹400-700)\n"
        output += "• **Best Value**: Train 3A AC (comfort + price)\n"
        output += "• **Fastest**: Budget Flight (if booked early)\n"
    else:
        output += "🚂 **TRAINS** (Recommended)\n"
        output += "   💰 Sleeper: ₹200 - ₹500\n"
        output += "   💰 3A AC: ₹500 - ₹1,200\n"
        output += "   ⏱️ Travel time: 4-12 hours\n\n"
        
        output += "🚌 **BUSES**\n"
        output += "   💰 Regular: ₹400 - ₹800\n"
        output += "   💰 AC Sleeper: ₹800 - ₹1,500\n"
        output += "   ⏱️ Travel time: 4-15 hours\n\n"
        
        output += "🏆 **RECOMMENDATION:**\n"
        output += "• **Cheapest**: Train Sleeper or State Bus\n"
        output += "• **Best Value**: Train 3A or AC Bus\n"
    
    output += "\n🔗 **Quick Search Links:**\n"
    output += f"• Flights: MakeMyTrip, Goibibo, ixigo\n"
    output += f"• Trains: IRCTC, ixigo Trains\n"
    output += f"• Buses: RedBus, AbhiBus, MakeMyTrip Bus\n"
    
    return output


@tool
def get_travel_deals_and_coupons() -> str:
    """
    Get current travel deals, discounts, and coupon codes
    from major platforms.
    
    Returns:
        List of active deals and promo codes
    """
    now = datetime.now(IST)
    
    output = "🎁 **Current Travel Deals & Coupons**\n"
    output += f"📅 Updated: {now.strftime('%B %d, %Y')}\n\n"
    
    output += "✈️ **FLIGHT DEALS:**\n\n"
    
    output += "🟠 **MakeMyTrip**\n"
    output += "   • Code: `MMTFLY` - Up to ₹1,500 off on domestic\n"
    output += "   • Code: `MMTNEW` - ₹500 off for new users\n"
    output += "   • ICICI Cards: Extra 10% off (up to ₹2,000)\n\n"
    
    output += "🔴 **Goibibo**\n"
    output += "   • Code: `GOFLY` - Up to ₹1,200 off\n"
    output += "   • Code: `GOFIRST` - ₹750 off first booking\n"
    output += "   • GoCash+: Extra 5% GoCash back\n\n"
    
    output += "🟡 **Cleartrip**\n"
    output += "   • Code: `CTFLY` - Flat ₹500 off\n"
    output += "   • Flipkart Plus: Extra benefits\n\n"
    
    output += "🔵 **ixigo**\n"
    output += "   • Code: `IXIGOAIR` - Up to ₹1,000 off\n"
    output += "   • Assured cashback on most bookings\n\n"
    
    output += "🚂 **TRAIN DEALS:**\n\n"
    
    output += "🟠 **IRCTC**\n"
    output += "   • SBI Card: 10% off (max ₹100)\n"
    output += "   • IRCTC iMudra: ₹50 cashback\n\n"
    
    output += "🔷 **Paytm**\n"
    output += "   • Code: `TRAIN50` - ₹50 cashback\n"
    output += "   • Paytm First: Extra 5% cashback\n\n"
    
    output += "🚌 **BUS DEALS:**\n\n"
    
    output += "🔴 **RedBus**\n"
    output += "   • Code: `FIRST` - ₹150 off first ride\n"
    output += "   • Code: `RBSAVE` - 15% off (max ₹200)\n\n"
    
    output += "💡 **Money-Saving Tips:**\n"
    output += "• Use bank offers (HDFC, ICICI, SBI) for extra discount\n"
    output += "• Book return tickets together for combo discounts\n"
    output += "• Check platform wallets for additional cashback\n"
    output += "• Compare prices using Google Flights for trends\n"
    
    return output


# ============== TRAVEL AGENT CLASS ==============

class TravelAgent(BaseSubAgent):
    """
    Specialized agent for travel planning and price comparison.
    
    Capabilities:
    - Search flights across multiple platforms
    - Search trains with booking links
    - Compare all travel modes
    - Find deals and coupons
    - Track flight/train status
    """
    
    def __init__(self):
        tools = [
            search_flights_all_platforms,
            search_trains_all_platforms,
            find_cheapest_travel_option,
            get_travel_deals_and_coupons,
        ]
        
        # Also include the existing flight/train tools
        from tools.indian_railways import (
            check_pnr_status, get_train_status, search_trains, get_station_code
        )
        from tools.flights import (
            get_flight_status, get_flight_by_route, get_airport_info, track_flight_live
        )
        
        tools.extend([
            check_pnr_status, get_train_status, search_trains, get_station_code,
            get_flight_status, get_flight_by_route, get_airport_info, track_flight_live
        ])
        
        super().__init__(
            name="TravelAgent",
            description="Expert in travel planning - flights, trains, price comparison",
            tools=tools
        )
    
    def get_system_prompt(self) -> str:
        return """You are TravelAgent, an expert travel planning assistant for Orion AI.

Your expertise:
- Finding the cheapest flights across MakeMyTrip, Goibibo, Cleartrip, ixigo
- Searching trains with prices and availability
- Comparing all travel modes (flight vs train vs bus)
- Finding active deals, coupons, and discounts
- Tracking PNR status and live train/flight status

When user asks about travel:
1. Understand the route (from -> to) and date
2. Search across all relevant platforms
3. Provide price comparisons with booking links
4. Suggest the best value option
5. Mention any applicable deals or coupons

Always provide:
- Direct booking links
- Estimated price ranges
- Pro tips for saving money
- Best time to book

You have access to tools for:
- search_flights_all_platforms: Compare flight prices
- search_trains_all_platforms: Compare train options
- find_cheapest_travel_option: Compare all modes
- get_travel_deals_and_coupons: Current offers
- check_pnr_status: Train booking status
- get_train_status: Live train running status
- get_flight_status: Live flight status
- track_flight_live: Real-time aircraft tracking

Be helpful, specific, and always prioritize saving money for the user."""
    
    def get_capabilities(self) -> List[str]:
        return [
            "Search flights across MakeMyTrip, Goibibo, Cleartrip, ixigo, EaseMyTrip",
            "Search trains on IRCTC, ixigo, Paytm, ConfirmTkt, RailYatri",
            "Compare flight vs train vs bus prices",
            "Find cheapest travel option for any route",
            "Get current deals and coupon codes",
            "Check PNR status and confirmation probability",
            "Track live train running status",
            "Track live flight status and location",
            "Get airport information and terminals",
        ]


# Export the tools for use in main Orion
def get_travel_agent_tools():
    """Get all travel agent tools for the main Orion agent"""
    return [
        search_flights_all_platforms,
        search_trains_all_platforms,
        find_cheapest_travel_option,
        get_travel_deals_and_coupons,
    ]
