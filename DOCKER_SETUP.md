# Docker Setup for Maccabi Activity Scraper

This guide shows how to create a reproducible Android Virtual Device (AVD) environment using Docker for automated Maccabi activity scraping.

## 🏗️ Architecture

The Docker setup includes:
- **Android Emulator**: Samsung Galaxy S10e with API 30 (Android 11)
- **Python Environment**: All required packages for the scraper
- **Persistent Storage**: AVD data and output files
- **Automation Scripts**: Easy setup and execution

## 📋 Prerequisites

### System Requirements
- **Docker** and **Docker Compose** installed
- **At least 8GB RAM** (12GB+ recommended)
- **20GB+ free disk space**
- **CPU with virtualization support**

### Platform-Specific Requirements

#### Linux (Recommended)
```bash
# Enable KVM for hardware acceleration
sudo usermod -a -G kvm $USER
# Reboot after adding user to kvm group
```

#### macOS
```bash
# Docker Desktop with sufficient resources allocated
# Recommended: 6GB+ RAM, 4+ CPUs in Docker Desktop settings
```

#### Windows
```bash
# Docker Desktop with WSL2 backend
# Enable virtualization in BIOS
```

## 🚀 Quick Start

### 1. Build and Start the Environment
```bash
# Set up Docker environment (without APK)
./scripts/setup_and_run.sh setup

# OR set up with Maccabi APK
./scripts/setup_and_run.sh setup /path/to/maccabi.apk
```

### 2. Manual App Setup (if no APK provided)
```bash
# Open shell in container
./scripts/setup_and_run.sh shell

# Install APK manually
adb install /path/to/maccabi.apk

# Or use Google Play Store in emulator
```

### 3. Run the Scraper
```bash
# Run automated scraping
./scripts/setup_and_run.sh run
```

## 📁 Project Structure
```
upapp/
├── docker/
│   └── avd/
│       ├── config.ini          # AVD configuration
│       └── maccabi_scraper_avd.ini
├── scripts/
│   └── setup_and_run.sh        # Main automation script
├── output/                     # Scraping results
├── logs/                       # Container logs
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Service orchestration
├── requirements.txt            # Python dependencies
└── DOCKER_SETUP.md            # This file
```

## ⚙️ Configuration

### AVD Specifications (Matching Your Current Setup)
- **Device**: Samsung Galaxy S10e
- **Android Version**: 11 (API 30)
- **Architecture**: arm64-v8a
- **Screen**: 1080x2280, 480 DPI
- **RAM**: 2GB
- **Storage**: 6GB system partition
- **Features**: Google APIs, GPS, Camera

### Environment Variables
```yaml
# In docker-compose.yml
DEVICE: "Samsung Galaxy S10e"
API_LEVEL: 30
TARGET: google_apis
ABI: arm64-v8a
EMULATOR_TIMEOUT: 300
```

## 🔧 Available Commands

```bash
# Setup and management
./scripts/setup_and_run.sh setup [apk_path]  # Initial setup
./scripts/setup_and_run.sh run              # Run scraper
./scripts/setup_and_run.sh shell            # Open container shell
./scripts/setup_and_run.sh logs             # View logs
./scripts/setup_and_run.sh stop             # Stop services
./scripts/setup_and_run.sh clean            # Clean up

# Docker commands
docker-compose up -d                         # Start services
docker-compose down                          # Stop services
docker-compose logs -f                       # View logs
```

## 📊 Monitoring and Debugging

### Check Emulator Status
```bash
# Inside container
docker exec maccabi-android-scraper adb devices
docker exec maccabi-android-scraper adb shell getprop sys.boot_completed
```

### View Emulator Screen (if VNC enabled)
```bash
# Open in browser
http://localhost:6080
```

### Access Container Shell
```bash
./scripts/setup_and_run.sh shell
# OR
docker exec -it maccabi-android-scraper bash
```

## 🎯 Automation Workflow

### Full Automation Pipeline
```bash
# 1. Initial setup
./scripts/setup_and_run.sh setup /path/to/maccabi.apk

# 2. Run scraper multiple times
./scripts/setup_and_run.sh run

# 3. Check results
ls -la output/
```

### Scheduled Automation (Cron)
```bash
# Add to crontab for daily scraping
0 2 * * * cd /path/to/upapp && ./scripts/setup_and_run.sh run
```

## 🔍 Troubleshooting

### Common Issues

#### Emulator Won't Start
```bash
# Check logs
./scripts/setup_and_run.sh logs

# Try with more resources
# Edit docker-compose.yml:
# - increase hw.ramSize in config.ini
# - add more CPUs to docker service
```

#### ADB Connection Issues
```bash
# Restart ADB
docker exec maccabi-android-scraper adb kill-server
docker exec maccabi-android-scraper adb start-server
```

#### Performance Issues
```bash
# Linux: Ensure KVM is enabled
ls -la /dev/kvm
groups | grep kvm

# macOS/Windows: Increase Docker Desktop resources
# Docker Desktop > Settings > Resources > Advanced
```

#### AVD Creation Fails
```bash
# Manually create AVD
docker exec -it maccabi-android-scraper bash
echo 'no' | avdmanager create avd -n maccabi_scraper_avd -k 'system-images;android-30;google_apis;arm64-v8a' --force
```

### Debug Mode
```bash
# Run container in debug mode
docker run -it --rm \
  --privileged \
  -p 5037:5037 \
  -p 5554:5554 \
  -p 5555:5555 \
  maccabi-scraper bash
```

## 📈 Performance Optimization

### For Better Performance
1. **Enable hardware acceleration** (KVM on Linux)
2. **Allocate sufficient resources** to Docker
3. **Use SSD storage** for Docker volumes
4. **Close unnecessary applications** during scraping

### Resource Usage
- **Typical RAM usage**: 4-6GB
- **CPU usage**: 2-4 cores during emulator startup
- **Disk space**: 15-20GB for full setup
- **Network**: Minimal (app downloads only)

## 🔒 Security Considerations

- Container runs with **necessary privileges** for emulator
- **No sensitive data** should be stored in container
- **Use environment variables** for any credentials
- **Regularly update** base images for security patches

## 📚 Advanced Usage

### Custom AVD Configuration
Edit `docker/avd/config.ini` to modify:
- Screen resolution
- RAM allocation
- Hardware features
- Performance settings

### Multiple Scraper Instances
```bash
# Run multiple containers with different ports
docker-compose -f docker-compose-instance2.yml up -d
```

### CI/CD Integration
```yaml
# GitHub Actions example
- name: Run Maccabi Scraper
  run: |
    ./scripts/setup_and_run.sh setup
    ./scripts/setup_and_run.sh run
    # Upload results to artifact storage
```

## 📞 Support

For issues specific to:
- **Docker setup**: Check container logs and system requirements
- **Android emulator**: Verify AVD configuration and system virtualization
- **Scraper functionality**: Review the main scraper documentation in README.md

## 🔄 Updates and Maintenance

### Updating the Setup
```bash
# Pull latest changes
git pull

# Rebuild container
./scripts/setup_and_run.sh clean
./scripts/setup_and_run.sh setup
```

### Backup Important Data
```bash
# Backup AVD data
docker cp maccabi-android-scraper:/opt/android/avd ./avd_backup

# Backup results
cp -r output/ backup_$(date +%Y%m%d)/
```
