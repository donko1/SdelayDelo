from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from tasks.models import Note  
import random
from datetime import timedelta

class Command(BaseCommand):
    help = 'Генерирует 450 тестовых заметок (по 150 на каждую дату) для первого пользователя'

    def handle(self, *args, **options):
        User = get_user_model()
        
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={
                'email': 'test@example.com',
                'is_active': True
            }
        )
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(f'Создан тестовый пользователь: {user.username}')
        
        adjectives = ['Важная', 'Срочная', 'Идея', 'Задача', 'Напоминание', 'Мысль', 
                     'Встреча', 'План', 'Цель', 'Проект', 'Личная', 'Рабочая',
                     'Ежедневная', 'Неотложная', 'Креативная']
        
        date_ranges = [
            (timezone.now().date(), 150),  
            (timezone.now().date() - timedelta(days=1), 150),
            (timezone.now().date() - timedelta(days=2), 150) 
        ]
        
        total_created = 0
        
        for note_date, count in date_ranges:
            self.stdout.write(f'Создаем {count} заметок для даты {note_date}')
            
            for i in range(count):
                adjective = adjectives[i % len(adjectives)]
                title = f"{adjective} {i + 1}"
                description = f"Автоматически сгенерированная заметка от {note_date}. Это заметка №{i + 1} с заголовком '{title}'."
                
                Note.objects.create(
                    user=user,
                    title=title,
                    description=description,
                    date_of_note=note_date,
                    is_pinned=random.choice([True, False]),
                    is_archived=random.choice([True, False])
                )
            
            total_created += count
            self.stdout.write(f'Создано {count} заметок для {note_date}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно создано {total_created} заметок (по 150 на сегодня, вчера и позавчера) для пользователя {user.username}'
            )
        )