import secrets
import string

def generate_hex_key(num_bytes=32):
    """
    Generate a secure random key in hexadecimal format.
    :param num_bytes: Number of random bytes (default 32 = 256 bits)
    :return: Hexadecimal string
    """
    if not isinstance(num_bytes, int) or num_bytes <= 0:
        raise ValueError("num_bytes must be a positive integer")
    return secrets.token_hex(num_bytes)

def generate_urlsafe_key(num_bytes=32):
    """
    Generate a secure random URL-safe key.
    :param num_bytes: Number of random bytes (default 32)
    :return: URL-safe Base64 encoded string
    """
    if not isinstance(num_bytes, int) or num_bytes <= 0:
        raise ValueError("num_bytes must be a positive integer")
    return secrets.token_urlsafe(num_bytes)

def generate_password(length=16):
    """
    Generate a secure random password with letters, digits, and symbols.
    :param length: Length of the password (default 16)
    :return: Secure password string
    """
    if not isinstance(length, int) or length <= 0:
        raise ValueError("length must be a positive integer")
    
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

if __name__ == "__main__":
    # Example usage
    # print("Hex Key (256-bit):", generate_hex_key(32))
    # print("URL-safe Key (256-bit):", generate_urlsafe_key(32))
    # print("Secure Password (16 chars):", generate_password(16))
    filepath = r'C:\Users\wings\hng_intern\stage1\secret_keys.txt'
    with open(filepath, 'w') as f:
        f.write(f"Hex Key (256-bit): {generate_hex_key(32)}\n")
        f.write(f"URL-safe Key (256-bit): {generate_urlsafe_key(32)}\n")
        f.write(f"Secure Password (16 chars): {generate_password(16)}\n")
        

