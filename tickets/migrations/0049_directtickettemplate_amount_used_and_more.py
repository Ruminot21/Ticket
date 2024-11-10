# Generated by Django 4.2.15 on 2024-11-10 13:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0048_directtickettemplate_created_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='directtickettemplate',
            name='amount_used',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='directtickettemplate',
            name='order',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tickets.order'),
        ),
    ]