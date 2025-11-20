#!/bin/bash
# Demo: Validate River Dashboard from Laptop
# This script demonstrates the complete validation workflow

echo "🌊 River Dashboard Validation Demo 🚀"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if validator exists
if [ ! -f "validate_dashboard.py" ]; then
    echo "❌ validate_dashboard.py not found in current directory"
    echo "Please run this script from the docker/ directory"
    exit 1
fi

echo -e "${CYAN}Step 1: Testing live deployment${NC}"
echo "Command: python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev"
echo ""
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev

echo ""
echo -e "${GREEN}✅ Full validation complete!${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo -e "${CYAN}Step 2: Testing specific site (Town Creek)${NC}"
echo "Command: python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev --site 'Town Creek'"
echo ""
python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev --site "Town Creek"

echo ""
echo -e "${GREEN}✅ Single site validation complete!${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo -e "${CYAN}Step 3: Quick connectivity check${NC}"
echo "Command: curl -I https://docker-blue-sound-1751.fly.dev"
echo ""
curl -I https://docker-blue-sound-1751.fly.dev 2>&1 | head -5

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo -e "${GREEN}🎉 Demo Complete!${NC}"
echo ""
echo -e "${YELLOW}What you just saw:${NC}"
echo "1. ✅ Full validation of all 6 river sites"
echo "2. ✅ Single site validation (Town Creek)"
echo "3. ✅ HTTP connectivity check"
echo ""
echo -e "${YELLOW}Key features validated:${NC}"
echo "   ⭐ City abbreviations (ALBVL, HNTSV, CULMAN, FTPAYN, MADSNVL)"
echo "   🌊 River names and USGS links"
echo "   💧 Water levels (feet & CFS)"
echo "   📊 12-hour sparkline charts"
echo "   🌡️ Weather observations"
echo "   🌧️ Rainfall forecasts"
echo ""
echo -e "${CYAN}Try it yourself:${NC}"
echo "   python3 validate_dashboard.py https://docker-blue-sound-1751.fly.dev"
echo ""
echo "Happy paddling! 🚣‍♂️🌊"
