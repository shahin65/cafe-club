from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods

from banners.catalog import LAB_PACKAGES, LAB_SKU_GATEWAYS, ensure_lab_packages, lab_package
from banners.models import PaymentTransaction
from banners.pay_views import start_checkout

staff_lab = staff_member_required(login_url="admin:login")


@staff_lab
@require_GET
def lab_home(request):
    ensure_lab_packages()
    packages = {item["sku"]: lab_package(item["sku"]) for item in LAB_PACKAGES}
    recent = (
        PaymentTransaction.objects.filter(user=request.user, package__kind="lab")
        .select_related("package")
        .order_by("-created_at", "-id")[:8]
    )
    return render(
        request,
        "account/dev_lab.html",
        {
            "bazaar_pack": packages.get(LAB_PACKAGES[0]["sku"]),
            "myket_pack": packages.get(LAB_PACKAGES[1]["sku"]),
            "bazaar_sku": LAB_PACKAGES[0]["sku"],
            "myket_sku": LAB_PACKAGES[1]["sku"],
            "recent": recent,
            "install_source": getattr(request, "app_source", "") or "",
        },
    )


@staff_lab
@require_http_methods(["POST"])
def lab_buy(request, sku):
    gateway = LAB_SKU_GATEWAYS.get(sku)
    package = lab_package(sku)
    if not gateway or not package:
        raise Http404()
    return start_checkout(request, package, fail_url="dev_lab", return_to="lab", gateway=gateway)
