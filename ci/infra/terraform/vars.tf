variable "common" {
  type = map(string)
  default = {
    clone         = "kube-ubuntu2004"
    search_domain = "lan.tribe29.com"
    target_node   = "pve-fra-001"
    nameserver    = "10.200.0.1"
    ssh_pub_key   = "ecdsa-sha2-nistp521 AAAAE2VjZHNhLXNoYTItbmlzdHA1MjEAAAAIbmlzdHA1MjEAAACFBAErT1h+mGLJChZJAPUxpIU+2HDzfXNItmppKLXmKLhILyMiM7+/YWR3ZOQkzmy+jAyJQnLXffotrGj+10LR10IRKADheUXVutnIy7N655ljpSvlAvR3Gwpu2TRfyTNPWeD6sxO1SqW7kK7dG8kCmxAopJOLqAR7BhDGKwpVt627BqaifA== test@kube"
    ciuser        = "test"
    cipass        = "test"
  }
}

variable "masters" {
  type = map(map(string))
  default = {
    kubernetes-tests-master = {
      id     = "800"
      cpu    = "kvm64"      
      cores  = 2
      memory = 2048
      disk   = "20G"
      cidr   = "10.200.0.51/24"
      gw     = "10.200.0.1"
      ip     = "10.200.0.1"
    }
  }
}

variable "nodes" {
  type = map(map(string))
  default = {
    kubernetes-tests-node1 = {
      id     = "801"
      cpu    = "kvm64"      
      cores  = 2
      memory = 2048
      disk   = "20G"
      cidr   = "10.200.0.52/24"
      gw     = "10.200.0.1"
      ip     = "10.200.0.52"
    },
    kubernetes-tests-node2 = {
      id     = "802"
      cpu    = "kvm64"      
      cores  = 2
      memory = 2048
      disk   = "20G"
      cidr   = "10.200.0.53/24"
      gw     = "10.200.0.1"
      ip     = "10.200.0.53"
    }
  }
}
