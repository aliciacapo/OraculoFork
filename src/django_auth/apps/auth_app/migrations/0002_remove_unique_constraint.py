# Generated migration to remove unique constraint on AccessToken
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('auth_app', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='accesstoken',
            unique_together=set(),
        ),
    ]