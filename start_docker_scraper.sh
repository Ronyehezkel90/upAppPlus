#!/bin/bash

echo "🚀 Maccabi Activity Scraper - Docker Quick Start"
echo "================================================="

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is running"

# Check if docker-compose is available
if ! command -v docker-compose >/dev/null 2>&1; then
    echo "❌ docker-compose not found. Please install docker-compose."
    exit 1
fi

echo "✅ docker-compose is available"

# Create directories
mkdir -p output logs

echo ""
echo "📁 Project structure created:"
echo "   ✓ output/  - Scraping results will be saved here"
echo "   ✓ logs/    - Container logs will be saved here"

echo ""
echo "🔧 Your Docker setup includes:"
echo "   ✓ Samsung Galaxy S10e emulator (API 30, Android 11)"
echo "   ✓ 1080x2280 screen resolution"
echo "   ✓ arm64-v8a architecture"
echo "   ✓ Google APIs enabled"
echo "   ✓ Python scraper environment"

echo ""
echo "🎯 Next steps:"
echo ""
echo "1. Set up the Docker environment:"
echo "   ./scripts/setup_and_run.sh setup"
echo ""
echo "   OR with Maccabi APK:"
echo "   ./scripts/setup_and_run.sh setup /path/to/maccabi.apk"
echo ""
echo "2. Run the scraper:"
echo "   ./scripts/setup_and_run.sh run"
echo ""
echo "3. Other useful commands:"
echo "   ./scripts/setup_and_run.sh shell    # Open container shell"
echo "   ./scripts/setup_and_run.sh logs     # View logs"
echo "   ./scripts/setup_and_run.sh stop     # Stop services"
echo "   ./scripts/setup_and_run.sh clean    # Clean up everything"

echo ""
echo "📚 For detailed documentation, see:"
echo "   - DOCKER_SETUP.md (Docker-specific setup)"
echo "   - README.md (General scraper documentation)"

echo ""
echo "⚠️  Requirements:"
echo "   - At least 8GB RAM (12GB+ recommended)"
echo "   - 20GB+ free disk space"
echo "   - Virtualization enabled in BIOS (for performance)"

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo ""
    echo "🐧 Linux detected - for best performance:"
    echo "   sudo usermod -a -G kvm \$USER"
    echo "   # Then reboot to enable KVM acceleration"
fi

echo ""
echo "🚀 Ready to start? Run:"
echo "   ./scripts/setup_and_run.sh setup"
