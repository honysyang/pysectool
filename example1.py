import subprocess

def check_ping(): 
    """要求用户输入 IP 地址，并检测该 IP 是否可以 ping 通"""
    ip = input("请输入要检测的 IP 地址: ")
    try:
        # 在 Linux 系统上使用 ping 命令，发送 4 个数据包
        result = subprocess.run(['ping', '-c', '4', ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            print(f"IP {ip} 可以 ping 通。")
        else:
            print(f"IP {ip} 无法 ping 通。")
    except Exception as e:
        print(f"检测过程中出现错误: {e}")

if __name__ == "__main__":
    check_ping()