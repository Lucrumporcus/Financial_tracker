from rest_framework_nested import routers

from .views import (
    CategoryViewSet,
    FinancialOperationViewSet,
    GroupMembershipViewSet,
    GroupViewSet,
)


router = routers.DefaultRouter()

router.register(
    r'groups',
    GroupViewSet,
    basename='group',
)


groups_router = routers.NestedDefaultRouter(
    router,
    r'groups',
    lookup='group',
)

groups_router.register(
    r'members',
    GroupMembershipViewSet,
    basename='group-members',
)

router.register(
    r'categories',
    CategoryViewSet,
    basename='category',
)

router.register(
    r'operations',
    FinancialOperationViewSet,
    basename='operation',
)

urlpatterns = router.urls + groups_router.urls