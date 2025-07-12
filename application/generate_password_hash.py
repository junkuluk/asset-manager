import bcrypt


def generate_hash(password):
    # 비밀번호를 바이트 문자열로 인코딩
    password_bytes = password.encode("utf-8")
    # 비밀번호를 해싱하고, 솔트(salt)는 자동으로 생성
    hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    # 해시값을 문자열로 디코딩하여 반환
    return hashed_password.decode("utf-8")


if __name__ == "__main__":
    user_password = input("해싱할 비밀번호를 입력하세요: ")
    hashed_value = generate_hash(user_password)
    print(f"\n생성된 비밀번호 해시 값:\n{hashed_value}")
    print("\n이 값을 Streamlit secrets.toml 파일에 저장하세요.")
