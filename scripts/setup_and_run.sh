#!/bin/bash

# Maccabi Scraper Docker Setup and Automation Script
# This script sets up the Android emulator and runs the scraper

set -e

echo "🚀 Setting up Maccabi Scraper Docker environment..."

# Create necessary directories
mkdir -p output logs

# Function to wait for emulator to be ready
wait_for_emulator() {
    echo "⏳ Waiting for Android emulator to be ready..."
    local timeout=300
    local elapsed=0
    
    while [ $elapsed -lt $timeout ]; do
        if docker exec maccabi-android-scraper adb devices | grep -q "device$"; then
            echo "✅ Emulator is ready!"
            return 0
        fi
        sleep 10
        elapsed=$((elapsed + 10))
        echo "   Still waiting... (${elapsed}s/${timeout}s)"
    done
    
    echo "❌ Timeout waiting for emulator"
    return 1
}

# Function to install APK if provided
install_maccabi_app() {
    local apk_path=$1
    if [ -n "$apk_path" ] && [ -f "$apk_path" ]; then
        echo "📱 Installing Maccabi app..."
        docker cp "$apk_path" maccabi-android-scraper:/tmp/maccabi.apk
        docker exec maccabi-android-scraper adb install -r /tmp/maccabi.apk
        echo "✅ Maccabi app installed"
    else
        echo "⚠️  No APK provided. Please install Maccabi app manually."
        echo "   You can copy APK using: docker cp your_maccabi.apk maccabi-android-scraper:/tmp/"
        echo "   Then install with: docker exec maccabi-android-scraper adb install /tmp/maccabi.apk"
    fi
}

# Function to run the scraper
run_scraper() {
    echo "🏃 Running Maccabi activity scraper..."
    
    # Copy latest scraper code
    docker cp scraper/ maccabi-android-scraper:/app/
    docker cp main.py maccabi-android-scraper:/app/
    
    # Run the scraper
    docker exec -it maccabi-android-scraper python3 /app/scraper/maccabi_activity_scraper.py
    
    # Copy results back
    echo "📄 Copying results..."
    docker cp maccabi-android-scraper:/app/maccabi_activities_*.json ./output/ 2>/dev/null || true
    
    echo "✅ Scraping completed! Check ./output/ for results."
}

# Main execution
case "${1:-setup}" in
    "setup")
        echo "🔧 Setting up Docker environment..."
        docker-compose up -d
        wait_for_emulator
        install_maccabi_app "$2"
        echo "✅ Setup complete! Use '$0 run' to start scraping."
        ;;
    
    "run")
        echo "🏃 Running scraper..."
        if ! docker ps | grep -q maccabi-android-scraper; then
            echo "🔧 Container not running, starting up..."
            docker-compose up -d
            wait_for_emulator
        fi
        run_scraper
        ;;
    
    "shell")
        echo "🐚 Opening shell in container..."
        docker exec -it maccabi-android-scraper bash
        ;;
    
    "logs")
        echo "📋 Showing container logs..."
        docker-compose logs -f
        ;;
    
    "stop")
        echo "🛑 Stopping services..."
        docker-compose down
        ;;
    
    "clean")
        echo "🧹 Cleaning up..."
        docker-compose down -v
        docker rmi $(docker images -q maccabi-scraper* 2>/dev/null) 2>/dev/null || true
        echo "✅ Cleanup complete"
        ;;
    
    *)
        echo "Usage: $0 {setup|run|shell|logs|stop|clean}"
        echo ""
        echo "Commands:"
        echo "  setup [apk_path]  - Set up the Docker environment and optionally install APK"
        echo "  run              - Run the scraper"
        echo "  shell            - Open bash shell in container"
        echo "  logs             - Show container logs"
        echo "  stop             - Stop the services"
        echo "  clean            - Clean up containers and images"
        echo ""
        echo "Examples:"
        echo "  $0 setup                           # Set up without APK"
        echo "  $0 setup /path/to/maccabi.apk     # Set up and install APK"
        echo "  $0 run                             # Run the scraper"
        exit 1
        ;;
esac
