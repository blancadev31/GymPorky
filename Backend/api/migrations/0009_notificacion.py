# Funcionalidades adicionales: notificaciones automáticas (stock bajo y vencimiento de membresías).
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('api', '0008_caja_global_egresos')]
    operations = [
        migrations.CreateModel(
            name='Notificacion',
            fields=[
                ('id_notificacion', models.AutoField(primary_key=True, serialize=False)),
                ('tipo', models.CharField(max_length=30)),
                ('titulo', models.CharField(max_length=150)),
                ('mensaje', models.TextField()),
                ('pantalla', models.CharField(blank=True, max_length=40, null=True)),
                ('referencia', models.CharField(max_length=120)),
                ('leida', models.BooleanField(default=False)),
                ('enviada_correo', models.BooleanField(default=False)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('id_usuario', models.ForeignKey(db_column='id_usuario', on_delete=django.db.models.deletion.CASCADE,
                                                 related_name='notificaciones', to='api.usuario')),
            ],
            options={'db_table': 'notificacion', 'ordering': ['-fecha_creacion'],
                     'unique_together': {('id_usuario', 'referencia')}},
        ),
    ]
