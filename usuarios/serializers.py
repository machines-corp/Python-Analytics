from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from .models import CustomUser
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password


User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'company_name']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'password' in validated_data:
            validated_data['password'] = make_password(validated_data['password'])
        return super().update(instance, validated_data)


class RegisterSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2', 'role', 'company_name')
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate_username(self, value):
        username = value.lower().strip()
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError("Este nombre de usuario ya existe.")
        return username

    def validate_email(self, value):
        email = value.lower().strip()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("Este email ya está registrado.")
        return email

    def validate(self, attrs):
        # Confirmación de contraseña
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                "password2": "Las contraseñas no coinciden."
            })

        # Validación de contraseña con reglas de Django
        validate_password(attrs['password'])

        # Validación de empresa
        if attrs.get("role") == "company" and not attrs.get("company_name"):
            raise serializers.ValidationError({
                "company_name": "Debes ingresar el nombre de la empresa."
            })

        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        validated_data['username'] = validated_data['username'].lower().strip()

        user = User.objects.create_user(**validated_data)
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, attrs):
        username = attrs.get('username').lower().strip()
        password = attrs.get('password')

        user = authenticate(username=username, password=password)

        if not user:
            raise serializers.ValidationError("Credenciales inválidas.")

        attrs['user'] = user
        return attrs

