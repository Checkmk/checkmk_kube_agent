terraform {
  required_providers {
    proxmox = {
      source  = "telmate/proxmox"
      version = "2.9.3"
    }
  }
}

provider "proxmox" {
  pm_api_url = var.common.proxmox_url
}
