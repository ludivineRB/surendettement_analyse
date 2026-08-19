from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("assistant", "0003_conversations")]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="kind",
            field=models.CharField(
                choices=[("information", "Informations métier"), ("sql", "Analyse SQL")],
                default="information",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="conversationmessage",
            name="category",
            field=models.CharField(blank=True, max_length=48),
        ),
        migrations.AddField(
            model_name="conversationmessage",
            name="response_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="conversationmessage",
            name="generated_sql",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="conversationmessage",
            name="feedback",
            field=models.CharField(
                blank=True,
                choices=[("useful", "Utile"), ("not_useful", "Inutile")],
                max_length=16,
            ),
        ),
    ]
