import sys
import os

# Add backend to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.security.device_store import DeviceStore

def main():
    store = DeviceStore()
    
    while True:
        devices = store.list_devices()
        print("\n=== Dispositivos Pareados ===")
        if not devices:
            print("Nenhum dispositivo encontrado.")
        else:
            for idx, (d_id, info) in enumerate(devices.items()):
                print(f"[{idx}] {info['deviceName']}")
                print(f"    ID: {d_id}")
                print(f"    Criado em: {info['createdAt']}")
                print(f"    Último acesso: {info['lastAccess']}")
        print("=============================")
        print("\nComandos: (r) revogar, (q) sair")
        cmd = input("Digite o comando: ").strip().lower()
        
        if cmd == 'q':
            break
        elif cmd == 'r':
            d_id = input("Digite o ID exato do dispositivo para revogar: ").strip()
            if store.revoke_device(d_id):
                print(f"Dispositivo {d_id} revogado com sucesso!")
            else:
                print("Dispositivo não encontrado ou erro ao revogar.")
        else:
            print("Comando inválido.")

if __name__ == '__main__':
    main()
