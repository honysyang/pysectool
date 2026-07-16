"""示例：安全的 ping 检测工具。"""

import ipaddress
import subprocess


def validate_ip(value: str) -> str:
    """校验输入是否为合法 IP 地址（IPv4 或 IPv6）。

    Args:
        value: 用户输入字符串。

    Returns:
        合法的 IP 字符串。

    Raises:
        ValueError: 输入不是合法 IP 地址。
    """
    value = value.strip()
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError(f"输入的不是合法 IP 地址: {value}") from exc
    return value


def check_ping() -> None:
    """要求用户输入 IP 地址，并检测该 IP 是否可以 ping 通。"""
    try:
        ip = input("请输入要检测的 IP 地址: ")
        ip = validate_ip(ip)
    except (EOFError, KeyboardInterrupt):
        print("\n已取消输入。")
        return
    except ValueError as exc:
        print(f"输入校验失败: {exc}")
        return

    try:
        result = subprocess.run(
            ["ping", "-c", "4", ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print(f"IP {ip} 可以 ping 通。")
        else:
            print(f"IP {ip} 无法 ping 通。")
            if result.stderr:
                print(result.stderr.strip())
    except FileNotFoundError:
        print("错误: 找不到 ping 命令。")
    except OSError as exc:
        print(f"检测过程中出现错误: {exc}")


if __name__ == "__main__":
    check_ping()
