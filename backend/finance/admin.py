from django.contrib import admin

from .models import (
    User,
    Group,
    GroupMembership,
    Category,
    FinancialOperation,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'email',
        'created_at',
        'is_staff',
    )
    search_fields = (
        'username',
        'email',
    )


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'created_at',
    )
    search_fields = (
        'name',
    )


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'group',
        'role',
        'created_at',
    )
    list_filter = (
        'role',
    )
    search_fields = (
        'user__username',
        'group__name',
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'type',
        'group',
        'created_at',
    )
    list_filter = (
        'type',
    )
    search_fields = (
        'name',
    )


@admin.register(FinancialOperation)
class FinancialOperationAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'type',
        'amount',
        'category',
        'user',
        'group',
    )
    list_filter = (
        'type',
        'date',
    )
    search_fields = (
        'description',
        'user__username',
        'category__name',
    )