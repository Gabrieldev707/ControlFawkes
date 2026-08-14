"""Gera o certificado local que libera o microfone no celular.

Por que isto existe: `getUserMedia` só funciona em contexto seguro. Aberto por
`http://192.168.x.x:5173`, o Safari do iPhone nem expõe `navigator.mediaDevices`
— o botão de voz fica indisponível e não há configuração que resolva. A única
saída é servir o controle por HTTPS.

Como o certificado é assinado pela própria máquina, ele precisa entrar no
endereço exato pelo qual o celular acessa. Por isso o script descobre o IP da
rede local e o inclui no certificado: sem esse nome dentro dele, o iOS recusa a
conexão mesmo depois de o certificado ser confiado.

Uso:
    .\\.venv\\Scripts\\python.exe scripts/gerar_certificado.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from ipaddress import IPv4Address, ip_address
from pathlib import Path
import socket
import sys


# Um ano: tempo de sobra para uso doméstico, e curto o bastante para o
# certificado não virar um objeto esquecido na máquina.
VALIDADE_DIAS = 365
PASTA_PADRAO = Path(__file__).resolve().parent.parent / "data" / "certs"


def enderecos_locais() -> list[str]:
    """Endereços pelos quais o controle pode ser aberto nesta máquina."""
    nomes = {"localhost", socket.gethostname().lower()}
    enderecos = {"127.0.0.1", "::1"}

    for informacao in socket.getaddrinfo(socket.gethostname(), None):
        endereco = informacao[4][0]
        try:
            analisado = ip_address(endereco)
        except ValueError:
            continue
        # Só IPv4 privado: é o que o roteador entrega ao celular. Endereços
        # públicos não devem entrar num certificado de uso doméstico.
        if isinstance(analisado, IPv4Address) and analisado.is_private:
            enderecos.add(endereco)

    return sorted(nomes) + sorted(enderecos)


def gerar(pasta: Path = PASTA_PADRAO) -> tuple[Path, Path]:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        raise SystemExit(
            "Falta a biblioteca cryptography. Rode:\n"
            "    .\\.venv\\Scripts\\python.exe -m pip install cryptography",
        )

    pasta.mkdir(parents=True, exist_ok=True)
    caminho_cert = pasta / "controlfawkes.crt"
    caminho_chave = pasta / "controlfawkes.key"

    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "ControlFawkes Local"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ControlFawkes"),
    ])

    alternativos: list[x509.GeneralName] = []
    identificadores = enderecos_locais()
    for identificador in identificadores:
        try:
            alternativos.append(x509.IPAddress(ip_address(identificador)))
        except ValueError:
            alternativos.append(x509.DNSName(identificador))
            # O iPhone costuma resolver a máquina por mDNS, com sufixo .local.
            if not identificador.endswith(".local") and identificador != "localhost":
                alternativos.append(x509.DNSName(f"{identificador}.local"))

    agora = datetime.now(timezone.utc)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(minutes=5))
        .not_valid_after(agora + timedelta(days=VALIDADE_DIAS))
        .add_extension(x509.SubjectAlternativeName(alternativos), critical=False)
        # O iOS 13+ recusa certificado de servidor sem EKU de autenticação de
        # servidor, mesmo depois de confiado manualmente.
        .add_extension(
            x509.ExtendedKeyUsage([x509.ObjectIdentifier("1.3.6.1.5.5.7.3.1")]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(chave, hashes.SHA256())
    )

    caminho_chave.write_bytes(chave.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    caminho_cert.write_bytes(certificado.public_bytes(serialization.Encoding.PEM))

    print("Certificado gerado.\n")
    print(f"  certificado: {caminho_cert}")
    print(f"  chave:       {caminho_chave}")
    print("\nVale para:")
    for identificador in identificadores:
        print(f"  - {identificador}")

    endereco_rede = next(
        (
            identificador for identificador in identificadores
            if identificador not in {"127.0.0.1", "::1", "localhost"}
            and identificador[0].isdigit()
        ),
        None,
    )

    print("\nPara usar a voz no iPhone:")
    print("  1. npm run dev:https        (sobe frontend e backend por HTTPS)")
    if endereco_rede:
        print(f"  2. No iPhone, abra  https://{endereco_rede}:5173")
    else:
        print("  2. No iPhone, abra o endereço https:// mostrado pelo Vite")
    print("  3. O Safari vai avisar do certificado. Toque em Mostrar detalhes")
    print("     e depois em Visitar este site.")
    print("  4. Se o microfone continuar bloqueado, instale o certificado:")
    print("     abra o .crt pelo Safari, aceite o perfil, e então em")
    print("     Ajustes > Geral > Sobre > Certificados confiáveis, ligue este.")
    print("\nA pasta data/ é ignorada pelo Git: a chave privada não vai para o")
    print("repositório.")

    return caminho_cert, caminho_chave


if __name__ == "__main__":
    destino = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else PASTA_PADRAO
    gerar(destino)
