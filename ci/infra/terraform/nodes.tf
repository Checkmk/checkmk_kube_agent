# https://registry.terraform.io/providers/Telmate/proxmox/latest/docs

resource "proxmox_vm_qemu" "kubernetes-nodes" {
  for_each = var.nodes

  vmid        = each.value.id
  name        = each.key
  desc        = "Kubernetes Node"
  target_node = var.common.target_node
  agent       = 1
  clone       = var.common.clone
  memory      = each.value.memory
  cores       = each.value.cores
  cpu         = each.value.cpu

  pool = "Kubernetes-Test-VM"
  tags = "test"

  ciuser     = var.common.ciuser
  cipassword = var.common.cipass
  sshkeys    = var.common.ssh_pub_key

  ipconfig0 = "ip=${each.value.cidr},gw=${each.value.gw}"

  searchdomain = var.common.search_domain
  nameserver   = var.common.nameserver

  network {
    model  = "virtio"
    bridge = "vmbr1"
  }

  disk {
    type    = "scsi"
    storage = "nvme1"
    size    = each.value.disk
    ssd     = 1
    discard = "on"
  }

  provisioner "remote-exec" {

    connection {
      type     = "ssh"
      user     = var.common.ciuser
      private_key = file("../test@kube")
      host     = self.default_ipv4_address
    }

    inline = [
      "sudo modprobe br_netfilter",
      "sudo bash -c 'echo br_netfilter >> /etc/modules'",
      "sudo bash -c 'echo 1 > /proc/sys/net/ipv4/ip_forward'",
      "sudo bash -c 'echo net.ipv4.ip_forward = 1 > /etc/sysctl.d/50-kubernetes_ip_forward.conf'",
    ]
  }
}
