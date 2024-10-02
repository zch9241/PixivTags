# -*- coding=utf-8 -*-
# 参考：https://blog.csdn.net/jyttttttt/article/details/134972038
# 已弃用
# 

import os
import sqlite3
import json
import base64
import ctypes
from ctypes import wintypes

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


cwd = os.getcwd()
# 定义cookie、localstate、logindata三个文件的位置
cookie_path = cwd + r'\src\Cookies'
local_state_path = cwd + r'\src\Local State'
login_data_path = cwd + r'\src\Login Data'


# cookie_path = os.path.expanduser(os.path.join(
#     os.environ['LOCALAPPDATA'], r'Chromium\User Data\Default\Cookies'))
# local_state_path = os.path.join(
#     os.environ['LOCALAPPDATA'], r"Chromium\User Data\Local State")
# login_data_path =os.path.expanduser(os.path.join(
#     os.environ['LOCALAPPDATA'], r'Chromium\User Data\Default\Login Data'))

class AES_GCM:
    @staticmethod
    def encrypt(cipher, plaintext, nonce):
        cipher.mode = modes.GCM(nonce)
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext)
        return cipher, ciphertext, nonce

    @staticmethod
    def decrypt(cipher, ciphertext, nonce):
        cipher.mode = modes.GCM(nonce)
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext)

    @staticmethod
    def get_cipher(key):
        cipher = Cipher(algorithms.AES(key), None, backend=default_backend())
        return cipher


def dpapi_decrypt(encrypted):
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD),
                    ('pbData', ctypes.POINTER(ctypes.c_char))]

    try:
        p = ctypes.create_string_buffer(encrypted, len(encrypted))
        blobin = DATA_BLOB(ctypes.sizeof(p), p)
        blobout = DATA_BLOB()
        retval = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blobin), None, None, None, None, 0, ctypes.byref(blobout))
        if not retval:
            raise ctypes.WinError()
        result = ctypes.string_at(blobout.pbData, blobout.cbData)
        return result
    except Exception as e:
        print(f"Error in dpapi_decrypt: {e}")
        return None


def get_key_from_local_state():
    with open(local_state_path, encoding='utf-8', mode="r") as f:
        jsn = json.loads(str(f.readline()))
    return jsn["os_crypt"]["encrypted_key"]


def aes_decrypt(encrypted_txt):
    encoded_key = get_key_from_local_state()
    encrypted_key = base64.b64decode(encoded_key.encode())
    encrypted_key = encrypted_key[5:]
    key = dpapi_decrypt(encrypted_key)
    nonce = encrypted_txt[3:15]
    cipher = AES_GCM.get_cipher(key)
    return AES_GCM.decrypt(cipher, encrypted_txt[15:], nonce)


def chrome_decrypt(encrypted_txt):
    if encrypted_txt[:4] == b'x01x00x00x00':
        decrypted_txt = dpapi_decrypt(encrypted_txt)
        return decrypted_txt.decode()
    elif encrypted_txt[:3] == b'v10':
        decrypted_txt = aes_decrypt(encrypted_txt)
        return decrypted_txt[:-16].decode()
    else:
        print(f'未知的加密方式: {encrypted_txt}')


def query_cookie(host):
    if host:
        sql = f"select host_key, name, encrypted_value from cookies where host_key = '{host}'"
    else:
        sql = "select host_key, name, encrypted_value from cookies"
    with sqlite3.connect(cookie_path) as conn:
        result = conn.execute(sql).fetchall()

    return result

def query_logindata(url):
    if url:
        sql = f"select origin_url, username_value, password_value from logins where origin_url = '{url}'"
    else:
        sql = "select origin_url, username_value, password_value from logins"
    with sqlite3.connect(login_data_path) as conn:
        result = conn.execute(sql).fetchall()

    return result



if __name__ == '__main__':
    print("Decrypt Cookies:")
    cookies = query_cookie(".pixiv.net") # 可以传入参数筛选指定host_key
    for data in cookies:
        cok = data[0], data[1], chrome_decrypt(data[2])
        print(cok)

    # print()
    # print("Decrypt Login Data:")
    # logindata = query_logindata("") # 可以传入参数筛选指定url
    # for data in logindata:
    #     login = data[0], data[1], chrome_decrypt(data[2])
    #     print(login)


