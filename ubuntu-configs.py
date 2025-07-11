#!/usr/bin/env python3
"""
Ubuntu Hardware Profiler
Comprehensive system profiling tool for Ubuntu systems.
"""
import subprocess
import json
import re
import sys
from datetime import datetime
from pathlib import Path
class SystemProfiler:
    def __init__(self):
        self.profile_data = {}
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def run_command(self, cmd, shell=False):
        """Execute system command and return output"""
        try:
            if shell:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            else:
                result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=30)
            return result.stdout.strip() if result.returncode == 0 else None
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return None

    def get_basic_system_info(self):
        """Get basic system information"""
        print("🖥️  Gathering basic system information...")
        
        self.profile_data['basic_info'] = {
            'hostname': self.run_command('hostname'),
            'uptime': self.run_command('uptime'),
            'kernel_version': self.run_command('uname -r'),
            'architecture': self.run_command('uname -m'),
            'os_release': self.run_command('lsb_release -d'),
            'system_date': self.run_command('date'),
            'timezone': self.run_command('timedatectl show --property=Timezone --value'),
            'locale': self.run_command('locale | grep LANG'),
        }

    def get_hardware_info(self):
        """Get hardware information"""
        print("🔧 Gathering hardware information...")
        
        # CPU Information
        cpu_info = self.run_command('lscpu')
        cpu_model = self.run_command('grep "model name" /proc/cpuinfo | head -1')
        cpu_cores = self.run_command('nproc')
        
        # Memory Information
        memory_info = self.run_command('free -h')
        memory_total = self.run_command('grep MemTotal /proc/meminfo')
        
        # Storage Information
        disk_info = self.run_command('lsblk -o NAME,SIZE,TYPE,MOUNTPOINT')
        disk_usage = self.run_command('df -h')
        
        # Hardware details
        hardware_info = self.run_command('lshw -short')
        
        self.profile_data['hardware'] = {
            'cpu_info': cpu_info,
            'cpu_model': cpu_model,
            'cpu_cores': cpu_cores,
            'memory_info': memory_info,
            'memory_total': memory_total,
            'disk_info': disk_info,
            'disk_usage': disk_usage,
            'hardware_summary': hardware_info,
            'dmi_info': self.run_command('dmidecode -s system-product-name'),
            'manufacturer': self.run_command('dmidecode -s system-manufacturer'),
        }

    def get_gpu_info(self):
        """Get GPU information"""
        print("🎮 Gathering GPU information...")
        
        # NVIDIA GPU
        nvidia_info = self.run_command('nvidia-smi')
        nvidia_version = self.run_command('nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits')
        
        # General GPU info
        gpu_info = self.run_command('lspci | grep -i vga')
        gpu_details = self.run_command('lspci -v | grep -A 10 -i vga')
        
        # OpenGL info
        opengl_info = self.run_command('glxinfo | grep "OpenGL"')
        
        self.profile_data['gpu'] = {
            'nvidia_smi': nvidia_info,
            'nvidia_driver_version': nvidia_version,
            'gpu_devices': gpu_info,
            'gpu_details': gpu_details,
            'opengl_info': opengl_info,
        }

    def get_network_info(self):
        """Get network information"""
        print("🌐 Gathering network information...")
        
        # Network interfaces
        network_interfaces = self.run_command('ip addr show')
        network_routes = self.run_command('ip route show')
        
        # Network configuration
        dns_info = self.run_command('systemd-resolve --status')
        if not dns_info:
            dns_info = self.run_command('cat /etc/resolv.conf')
        
        # Network connectivity
        public_ip = self.run_command('curl -s ifconfig.me')
        
        self.profile_data['network'] = {
            'interfaces': network_interfaces,
            'routes': network_routes,
            'dns_info': dns_info,
            'public_ip': public_ip,
            'network_manager': self.run_command('nmcli device status'),
        }

    def get_package_info(self):
        """Get package and software information"""
        print("📦 Gathering package information...")
        
        # Package managers
        apt_packages = self.run_command('dpkg -l | wc -l')
        snap_packages = self.run_command('snap list')
        flatpak_packages = self.run_command('flatpak list')
        
        # Key software versions
        python_version = self.run_command('python3 --version')
        docker_version = self.run_command('docker --version')
        git_version = self.run_command('git --version')
        
        # System services
        systemd_services = self.run_command('systemctl list-units --type=service --state=running')
        
        self.profile_data['packages'] = {
            'total_apt_packages': apt_packages,
            'snap_packages': snap_packages,
            'flatpak_packages': flatpak_packages,
            'python_version': python_version,
            'docker_version': docker_version,
            'git_version': git_version,
            'running_services': systemd_services,
        }

    def get_security_info(self):
        """Get security-related information"""
        print("🔒 Gathering security information...")
        
        # Firewall status
        ufw_status = self.run_command('ufw status')
        
        # SELinux/AppArmor
        apparmor_status = self.run_command('aa-status')
        
        # Security updates
        security_updates = self.run_command('apt list --upgradable 2>/dev/null | grep -i security')
        
        self.profile_data['security'] = {
            'ufw_status': ufw_status,
            'apparmor_status': apparmor_status,
            'security_updates': security_updates,
        }

    def get_performance_info(self):
        """Get performance-related information"""
        print("⚡ Gathering performance information...")
        
        # System load
        load_avg = self.run_command('cat /proc/loadavg')
        
        # Process information
        top_processes = self.run_command('ps aux --sort=-%cpu | head -10')
        
        # I/O stats
        io_stats = self.run_command('iostat -x 1 1')
        
        self.profile_data['performance'] = {
            'load_average': load_avg,
            'top_processes': top_processes,
            'io_stats': io_stats,
        }

    def get_virtualization_info(self):
        """Get virtualization information"""
        print("🌐 Gathering virtualization information...")
        
        # Check if running in VM
        virt_info = self.run_command('systemd-detect-virt')
        
        # Docker info
        docker_info = self.run_command('docker info')
        docker_containers = self.run_command('docker ps -a')
        
        self.profile_data['virtualization'] = {
            'virtualization_type': virt_info,
            'docker_info': docker_info,
            'docker_containers': docker_containers,
        }

    def generate_report(self):
        """Generate comprehensive system report"""
        print(f"\n{'='*60}")
        print(f"SYSTEM PROFILE REPORT - {self.timestamp}")
        print(f"{'='*60}")
        
        # Basic System Information
        if 'basic_info' in self.profile_data:
            print(f"\n🖥️  BASIC SYSTEM INFORMATION")
            print(f"{'─'*40}")
            basic = self.profile_data['basic_info']
            print(f"Hostname: {basic.get('hostname', 'N/A')}")
            print(f"OS Release: {basic.get('os_release', 'N/A')}")
            print(f"Kernel: {basic.get('kernel_version', 'N/A')}")
            print(f"Architecture: {basic.get('architecture', 'N/A')}")
            print(f"Uptime: {basic.get('uptime', 'N/A')}")
            print(f"Timezone: {basic.get('timezone', 'N/A')}")
        
        # Hardware Information
        if 'hardware' in self.profile_data:
            print(f"\n🔧 HARDWARE INFORMATION")
            print(f"{'─'*40}")
            hw = self.profile_data['hardware']
            print(f"CPU Cores: {hw.get('cpu_cores', 'N/A')}")
            if hw.get('cpu_model'):
                print(f"CPU Model: {hw.get('cpu_model').split(':')[1].strip() if ':' in hw.get('cpu_model') else hw.get('cpu_model')}")
            print(f"Manufacturer: {hw.get('manufacturer', 'N/A')}")
            print(f"Product: {hw.get('dmi_info', 'N/A')}")
            if hw.get('memory_total'):
                print(f"Memory: {hw.get('memory_total').split()[1]} {hw.get('memory_total').split()[2]}")
        
        # GPU Information
        if 'gpu' in self.profile_data:
            print(f"\n🎮 GPU INFORMATION")
            print(f"{'─'*40}")
            gpu = self.profile_data['gpu']
            if gpu.get('gpu_devices'):
                print(f"GPU Devices: {gpu.get('gpu_devices')}")
            if gpu.get('nvidia_driver_version'):
                print(f"NVIDIA Driver: {gpu.get('nvidia_driver_version')}")
        
        # Network Information
        if 'network' in self.profile_data:
            print(f"\n🌐 NETWORK INFORMATION")
            print(f"{'─'*40}")
            net = self.profile_data['network']
            if net.get('public_ip'):
                print(f"Public IP: {net.get('public_ip')}")
        
        # Package Information
        if 'packages' in self.profile_data:
            print(f"\n📦 PACKAGE INFORMATION")
            print(f"{'─'*40}")
            pkg = self.profile_data['packages']
            print(f"Total APT Packages: {pkg.get('total_apt_packages', 'N/A')}")
            print(f"Python Version: {pkg.get('python_version', 'N/A')}")
            print(f"Docker Version: {pkg.get('docker_version', 'N/A')}")
            print(f"Git Version: {pkg.get('git_version', 'N/A')}")
        
        print(f"\n{'='*60}")
        print("Profile complete! Full details saved to JSON file.")
        print(f"{'='*60}")

    def save_json_report(self, filename=None):
        """Save detailed report to JSON file"""
        if not filename:
            filename = f"system_profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        self.profile_data['metadata'] = {
            'timestamp': self.timestamp,
            'profiler_version': '1.0',
            'python_version': sys.version,
        }
        
        with open(filename, 'w') as f:
            json.dump(self.profile_data, f, indent=2)
        
        print(f"Detailed report saved to: {filename}")

    def run_full_profile(self):
        """Run complete system profiling"""
        print("🚀 Starting comprehensive system profiling...")
        print("This may take a few minutes...\n")
        
        try:
            self.get_basic_system_info()
            self.get_hardware_info()
            self.get_gpu_info()
            self.get_network_info()
            self.get_package_info()
            self.get_security_info()
            self.get_performance_info()
            self.get_virtualization_info()
            
            self.generate_report()
            self.save_json_report()
            
        except KeyboardInterrupt:
            print("\n❌ Profiling interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Error during profiling: {e}")
            sys.exit(1)

def main():
    """Main function"""
    profiler = SystemProfiler()
    profiler.run_full_profile()

if __name__ == "__main__":
    main()