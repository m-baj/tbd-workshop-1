
module "vpc" {
  source       = "terraform-google-modules/network/google"
  version      = "~> 9.0.0"
  project_id   = var.project_name
  network_name = var.network_name
  routing_mode = "GLOBAL"
  subnets = [
    {
      subnet_name           = var.subnet_name
      subnet_ip             = var.subnet_address
      subnet_region         = var.region
      subnet_private_access = "true"
    }
  ]
  routes = [
    {
      name              = "egress-internet"
      description       = "route through IGW to access internet"
      destination_range = "0.0.0.0/0"
      next_hop_internet = "true"
    }
  ]
}
module "cloud-router" {
  source  = "terraform-google-modules/cloud-router/google"
  version = "~> 6.0.1"
  project = var.project_name
  region  = var.region
  network = module.vpc.network_id
  name    = "nat-router"
  nats = [{
    name = "nat-gateway"
  }]
}

resource "google_compute_router_nat" "nat" {
  name                               = "tbd-nat"
  router                             = "nat-router"
  region                             = var.region
  project                            = var.project_name
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

#Enables IAP tunneling
resource "google_compute_firewall" "fw-allow-ingress-from-iap" {
  name          = "fw-allow-ingress-iap"
  project       = var.project_name
  network       = module.vpc.network_id
  priority      = 1000
  direction     = "INGRESS"
  source_ranges = ["35.235.240.0/20"]

  allow {
    protocol = "tcp"
    ports    = ["22", "8443", "443", "80", "8000"]
  }

}

resource "google_compute_firewall" "default-internal-allow-all" {
  #checkov:skip=CKV2_GCP_12: "Ensure GCP compute firewall ingress does not allow unrestricted access to all ports"
  project       = var.project_name
  name          = "default-internal-allow-all"
  network       = module.vpc.network_id
  priority      = 65534
  direction     = "INGRESS"
  source_ranges = [var.subnet_address]

  allow {
    protocol = "all"
  }

}