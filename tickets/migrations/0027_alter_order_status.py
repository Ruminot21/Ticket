# Generated by Django 4.2.15 on 2024-08-20 06:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0026_profile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Pendiente'), ('PROCESSING', 'Procesando'), ('CONFIRMED', 'Confirmada'), ('ERROR', 'Error'), ('REFUNDED', 'Reembolsada')], default='PENDING', max_length=20),
        ),
    ]
