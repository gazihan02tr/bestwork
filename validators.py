"""
Input Validation Schemas
Marshmallow kullanarak güvenli input validation
"""
from marshmallow import Schema, fields, validates, ValidationError, validate
import re


class EmailField(fields.Email):
    """Custom email field with additional validation"""
    def _deserialize(self, value, attr, data, **kwargs):
        email = super()._deserialize(value, attr, data, **kwargs)
        return email.lower().strip()


class PhoneField(fields.String):
    """Phone number validation"""
    def _deserialize(self, value, attr, data, **kwargs):
        phone = super()._deserialize(value, attr, data, **kwargs)
        # Remove non-digit characters except +
        cleaned = ''.join(ch for ch in phone if ch.isdigit() or ch == '+')
        if len(cleaned) < 10:
            raise ValidationError('Geçerli bir telefon numarası giriniz.')
        return cleaned


class TCKNField(fields.String):
    """Turkish ID number validation"""
    def _deserialize(self, value, attr, data, **kwargs):
        tckn = super()._deserialize(value, attr, data, **kwargs)
        cleaned = ''.join(ch for ch in tckn if ch.isdigit())
        
        if len(cleaned) != 11:
            raise ValidationError('T.C. Kimlik numarası 11 haneli olmalıdır.')
        
        if cleaned[0] == '0':
            raise ValidationError('T.C. Kimlik numarası 0 ile başlayamaz.')
        
        return cleaned


class RegisterSchema(Schema):
    """User registration validation schema"""
    first_name = fields.String(required=True, validate=validate.Length(min=2, max=50))
    last_name = fields.String(required=True, validate=validate.Length(min=2, max=50))
    email = EmailField(required=True)
    phone = PhoneField(required=True)
    identity_number = TCKNField(required=True)
    password = fields.String(required=True, validate=validate.Length(min=6, max=128))
    password_confirm = fields.String(required=True)
    country_code = fields.String(required=True)
    membership_type = fields.String(
        required=True,
        validate=validate.OneOf(['bireysel', 'kurumsal'])
    )
    gender = fields.String(
        required=True,
        validate=validate.OneOf(['erkek', 'kadin', 'diger'])
    )
    dob_day = fields.Integer(required=True, validate=validate.Range(min=1, max=31))
    dob_month = fields.Integer(required=True, validate=validate.Range(min=1, max=12))
    dob_year = fields.Integer(required=True, validate=validate.Range(min=1900, max=2025))
    city = fields.String(required=True)
    district = fields.String(required=True)
    address = fields.String(required=True, validate=validate.Length(min=10, max=500))
    sponsor_code = fields.String(allow_none=True)
    agreement_distributor = fields.Boolean(required=True)
    agreement_kvkk = fields.Boolean(required=True)
    
    @validates('password_confirm')
    def validate_password_match(self, value):
        if value != self.context.get('password'):
            raise ValidationError('Şifreler eşleşmiyor.')


class LoginSchema(Schema):
    """Login validation schema"""
    identifier = fields.String(required=True, validate=validate.Length(min=3, max=100))
    password = fields.String(required=True, validate=validate.Length(min=1, max=128))


class ContactSchema(Schema):
    """Contact form validation schema"""
    full_name = fields.String(required=True, validate=validate.Length(min=3, max=100))
    phone = PhoneField(required=True)
    email = EmailField(required=True)
    city = fields.String(required=True, validate=validate.Length(min=2, max=50))
    message = fields.String(required=True, validate=validate.Length(min=10, max=1000))


class BankInfoSchema(Schema):
    """Bank information validation schema"""
    bank_name = fields.String(required=True, validate=validate.Length(min=2, max=100))
    account_holder = fields.String(required=True, validate=validate.Length(min=3, max=100))
    iban = fields.String(required=True, validate=validate.Length(min=26, max=34))
    
    @validates('iban')
    def validate_iban(self, value):
        # Basic IBAN format validation
        cleaned = value.replace(' ', '').upper()
        if not re.match(r'^TR\d{24}$', cleaned):
            raise ValidationError('Geçerli bir Türk IBAN numarası giriniz.')


class PasswordChangeSchema(Schema):
    """Password change validation schema"""
    current_password = fields.String(required=True)
    new_password = fields.String(required=True, validate=validate.Length(min=6, max=128))
    confirm_password = fields.String(required=True)
    
    @validates('confirm_password')
    def validate_password_match(self, value):
        if value != self.context.get('new_password'):
            raise ValidationError('Yeni şifreler eşleşmiyor.')
