from cryptography.hazmat.primitives.asymmetric import ed25519
import base64
import os

def generate_key_pair():
    # Generate private key
    private_key = ed25519.Ed25519PrivateKey.generate()
    
    # Get public key
    public_key = private_key.public_key()
    
    # Convert to bytes for storage
    private_bytes = private_key.private_bytes_raw()
    public_bytes = public_key.public_bytes_raw()
    
    # Convert to base64 for storage
    private_b64 = base64.b64encode(private_bytes).decode('utf-8')
    public_b64 = base64.b64encode(public_bytes).decode('utf-8')
    
    # Generate key ID from first 8 bytes of public key
    key_id = public_b64[:8]
    
    return key_id, private_b64, public_b64

if __name__ == "__main__":
    key_id, private_key, public_key = generate_key_pair()
    
    # Update .env file
    env_content = f"""
# Generated TUF keys
TUF_PRIVATE_KEY="{private_key}"
TUF_PUBLIC_KEY="{public_key}"
TUF_KEY_ID="{key_id}"
"""
    
    with open('.env', 'a') as f:
        f.write(env_content)
    
    print(f"Key ID: {key_id}")
    print("Keys have been added to .env file")