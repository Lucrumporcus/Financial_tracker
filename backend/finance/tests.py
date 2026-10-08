from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category, FinancialOperation, Group, GroupMembership, GroupRole


class RegistrationTests(APITestCase):
    def test_registration_creates_user_with_hashed_password(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'demo-user',
            'email': 'demo@example.com',
            'password': 'SafePassword123',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(username='demo-user')
        self.assertTrue(user.check_password('SafePassword123'))
        self.assertNotIn('password', response.data)

    def test_registration_rejects_short_password(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'demo-user',
            'email': 'demo@example.com',
            'password': 'short',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_template_registration_logs_user_in(self):
        response = self.client.post('/register/', {
            'username': 'web-user', 'email': 'web@example.com',
            'password': 'SafePassword123', 'password_confirm': 'SafePassword123',
        })
        self.assertRedirects(response, '/')
        self.assertTrue(get_user_model().objects.filter(username='web-user').exists())
        for path in ('/', '/groups/', '/operations/', '/statistics/'):
            self.assertEqual(self.client.get(path).status_code, 200)
        operations_page = self.client.get('/operations/').content.decode()
        self.assertEqual(operations_page.count('id="category-form"'), 1)
        self.assertIn('id="category-group"', operations_page)
        self.assertIn('id="categories-list"', operations_page)
        self.assertIn('id="filter-category"', operations_page)
        groups_page = self.client.get('/groups/').content.decode()
        self.assertIn('data-current-user=', groups_page)
        self.assertIn('участников', groups_page)

    def test_template_login_and_logout(self):
        get_user_model().objects.create_user(
            'login-user', email='login@example.com', password='SafePassword123',
        )
        response = self.client.post('/login/', {'username': 'login-user', 'password': 'SafePassword123'})
        self.assertRedirects(response, '/')
        self.assertEqual(self.client.get('/operations/').status_code, 200)
        self.assertRedirects(self.client.post('/logout/'), '/login/')
        self.assertRedirects(self.client.get('/'), '/login/?next=/')

    def test_browser_session_api_requires_csrf_and_can_create_group(self):
        user = get_user_model().objects.create_user(
            'session-api', email='session-api@example.com', password='SafePassword123',
        )
        client = Client(enforce_csrf_checks=True)
        self.assertTrue(client.login(username=user.username, password='SafePassword123'))
        client.get('/groups/')
        response = client.post('/api/groups/', data='{"name":"CSRF protected"}', content_type='application/json')
        self.assertEqual(response.status_code, 403)
        csrf = client.cookies['csrftoken'].value
        response = client.post(
            '/api/groups/', data='{"name":"CSRF protected"}', content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 201)


class GroupPermissionTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user('owner', email='owner@example.com', password='SafePassword123')
        self.member = User.objects.create_user('member', email='member@example.com', password='SafePassword123')
        self.observer = User.objects.create_user('observer', email='observer@example.com', password='SafePassword123')
        self.group = Group.objects.create(name='Shared')
        for user, role in ((self.owner, GroupRole.OWNER), (self.member, GroupRole.MEMBER), (self.observer, GroupRole.OBSERVER)):
            GroupMembership.objects.create(user=user, group=self.group, role=role)
        self.category = Category.objects.create(group=self.group, name='Food', type='EXPENSE')
        self.operation = FinancialOperation.objects.create(
            user=self.member, group=self.group, category=self.category,
            amount='20.00', type='EXPENSE', date='2026-10-08',
        )

    def test_member_can_read_group_but_cannot_manage_categories(self):
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get('/api/groups/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/groups/{self.group.id}/').status_code, 200)
        self.assertEqual(self.client.patch(f'/api/categories/{self.category.id}/', {'name': 'Changed'}, format='json').status_code, 403)
        self.assertEqual(self.client.post('/api/categories/', {'group': str(self.group.id), 'name': 'New', 'type': 'EXPENSE'}, format='json').status_code, 400)

    def test_owner_gets_clear_error_deleting_category_in_use(self):
        self.client.force_authenticate(self.owner)
        response = self.client.delete(f'/api/categories/{self.category.id}/')
        self.assertEqual(response.status_code, 400)

    def test_owner_can_create_group_category_and_member_cannot(self):
        data = {'name': 'Shared expenses', 'type': 'EXPENSE', 'group': str(self.group.id)}
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.post('/api/categories/', data, format='json').status_code, 400)

        self.client.force_authenticate(self.owner)
        response = self.client.post('/api/categories/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(response.data['group']), str(self.group.id))

    def test_observer_cannot_create_or_change_group_operations(self):
        self.client.force_authenticate(self.observer)
        data = {'group': str(self.group.id), 'category': str(self.category.id), 'amount': '5.00', 'type': 'EXPENSE', 'date': '2026-10-08'}
        self.assertEqual(self.client.post('/api/operations/', data, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/operations/{self.operation.id}/', {'description': 'x'}, format='json').status_code, 403)

    def test_member_can_edit_own_operation_and_owner_can_edit_member_operation(self):
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.patch(f'/api/operations/{self.operation.id}/', {'description': 'updated'}, format='json').status_code, 200)
        other = FinancialOperation.objects.create(user=self.owner, group=self.group, category=self.category, amount='3.00', type='EXPENSE', date='2026-10-08')
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.delete(f'/api/operations/{other.id}/').status_code, 403)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.delete(f'/api/operations/{other.id}/').status_code, 204)

    def test_owner_updates_group_and_member_can_create_group_operation(self):
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.patch(f'/api/groups/{self.group.id}/', {'name': 'forbidden'}, format='json').status_code, 403)
        data = {'group': str(self.group.id), 'category': str(self.category.id), 'amount': '9.25', 'type': 'EXPENSE', 'date': '2026-10-08'}
        response = self.client.post('/api/operations/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.client.force_authenticate(self.owner)
        response = self.client.patch(f'/api/groups/{self.group.id}/', {'name': 'Updated'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Updated')

    def test_only_owner_can_remove_members_and_last_owner_is_protected(self):
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.delete(f'/api/groups/{self.group.id}/members/{self.observer.group_memberships.first().id}/').status_code, 403)
        self.client.force_authenticate(self.owner)
        owner_membership = self.owner.group_memberships.get(group=self.group)
        response = self.client.delete(f'/api/groups/{self.group.id}/members/{owner_membership.id}/')
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(f'/api/groups/{self.group.id}/members/{owner_membership.id}/', {'role': 'MEMBER'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_owner_can_add_existing_user_by_username_only(self):
        invitee = get_user_model().objects.create_user(
            'invitee', email='invitee@example.com', password='SafePassword123',
        )
        self.client.force_authenticate(self.member)
        response = self.client.post(
            f'/api/groups/{self.group.id}/members/',
            {'invite_username': 'invitee', 'role': 'MEMBER'}, format='json',
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.owner)
        response = self.client.post(
            f'/api/groups/{self.group.id}/members/',
            {'invite_username': 'missing-user', 'role': 'MEMBER'}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            f'/api/groups/{self.group.id}/members/',
            {'invite_username': invitee.username, 'role': 'OBSERVER'}, format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['member_username'], invitee.username)
        duplicate = self.client.post(
            f'/api/groups/{self.group.id}/members/',
            {'invite_username': invitee.username, 'role': 'MEMBER'}, format='json',
        )
        self.assertEqual(duplicate.status_code, 400)

    def test_group_cannot_get_a_second_owner_through_api_or_database(self):
        invitee = get_user_model().objects.create_user(
            'second-owner', email='second-owner@example.com', password='SafePassword123',
        )
        self.client.force_authenticate(self.owner)

        create_response = self.client.post(
            f'/api/groups/{self.group.id}/members/',
            {'invite_username': invitee.username, 'role': GroupRole.OWNER},
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(GroupMembership.objects.filter(user=invitee, group=self.group).exists())

        member_membership = self.member.group_memberships.get(group=self.group)
        update_response = self.client.patch(
            f'/api/groups/{self.group.id}/members/{member_membership.id}/',
            {'role': GroupRole.OWNER},
            format='json',
        )
        self.assertEqual(update_response.status_code, status.HTTP_400_BAD_REQUEST)
        member_membership.refresh_from_db()
        self.assertEqual(member_membership.role, GroupRole.MEMBER)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GroupMembership.objects.create(
                    user=invitee, group=self.group, role=GroupRole.OWNER,
                )

    def test_owner_can_delete_group_with_its_related_data(self):
        self.client.force_authenticate(self.owner)
        response = self.client.delete(f'/api/groups/{self.group.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Group.objects.filter(pk=self.group.id).exists())


class CsvTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('csv-user', email='csv@example.com', password='SafePassword123')
        self.category = Category.objects.create(user=self.user, name='Salary', type='INCOME')
        self.client.force_authenticate(self.user)

    def test_csv_export_and_import_validation(self):
        FinancialOperation.objects.create(user=self.user, category=self.category, amount='123.45', type='INCOME', date='2026-10-08')
        response = self.client.get('/api/operations/export-csv/')
        self.assertEqual(response.status_code, 200)
        exported_csv = response.content.decode('utf-8-sig')
        self.assertIn('Дата;Тип;Сумма, ₽;Категория;Группа;Описание', exported_csv)
        self.assertIn('08.10.2026;Доход;123,45;Salary;Личная;', exported_csv)
        round_trip = SimpleUploadedFile('exported.csv', response.content, content_type='text/csv')
        round_trip_response = self.client.post('/api/operations/import-csv/', {'file': round_trip}, format='multipart')
        self.assertEqual(round_trip_response.status_code, 201)
        self.assertEqual(round_trip_response.data['created'], 1)

        bad_csv = SimpleUploadedFile('operations.csv', b'wrong,headers\n1,2\n', content_type='text/csv')
        response = self.client.post('/api/operations/import-csv/', {'file': bad_csv}, format='multipart')
        self.assertEqual(response.status_code, 400)

        good_row = f'date,type,amount,category,group,description\n2026-10-07,INCOME,45.00,{self.category.id},,refund\n'.encode()
        good_csv = SimpleUploadedFile('valid.csv', good_row, content_type='text/csv')
        response = self.client.post('/api/operations/import-csv/', {'file': good_csv}, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['created'], 1)

    def test_filters_and_summary_use_the_visible_filtered_queryset(self):
        FinancialOperation.objects.create(user=self.user, category=self.category, amount='12.00', type='INCOME', date='2026-10-08')
        response = self.client.get('/api/operations/?type=INCOME&date_from=2026-10-08')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        summary = self.client.get('/api/operations/summary/?date_from=2026-10-08')
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(float(summary.data['income']), 12.0)

    def test_personal_category_and_operation_crud(self):
        category_response = self.client.post('/api/categories/', {'name': 'Freelance', 'type': 'INCOME'}, format='json')
        self.assertEqual(category_response.status_code, 201)
        category_id = category_response.data['id']
        self.assertEqual(self.client.patch(f'/api/categories/{category_id}/', {'name': 'Contract'}, format='json').status_code, 200)
        operation = self.client.post('/api/operations/', {
            'category': category_id, 'amount': '99.50', 'type': 'INCOME', 'date': '2026-10-08',
        }, format='json')
        self.assertEqual(operation.status_code, 201)
        operation_id = operation.data['id']
        self.assertEqual(self.client.get(f'/api/operations/{operation_id}/').status_code, 200)
        self.assertEqual(self.client.patch(f'/api/operations/{operation_id}/', {'amount': '0'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(f'/api/operations/{operation_id}/').status_code, 204)
        self.assertEqual(self.client.delete(f'/api/categories/{category_id}/').status_code, 204)

    def test_csv_import_rolls_back_all_rows_when_any_row_is_invalid(self):
        initial_count = FinancialOperation.objects.count()
        contents = (
            f'date,type,amount,category,group,description\n'
            f'2026-10-07,INCOME,45.00,{self.category.id},,valid\n'
            f'2026-10-08,INVALID,20.00,{self.category.id},,invalid\n'
        ).encode()
        upload = SimpleUploadedFile('atomic.csv', contents, content_type='text/csv')
        response = self.client.post('/api/operations/import-csv/', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(FinancialOperation.objects.count(), initial_count)
