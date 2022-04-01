# https://registry.terraform.io/providers/Telmate/proxmox/latest/docs#pm_user

terraform {
  required_providers {
    proxmox = {
      source  = "telmate/proxmox"
      version = "2.9.3"
    }
  }
}

provider "proxmox" {
  pm_api_url = "https://pve-fra-001.tribe29.com:8006/api2/json"
}
