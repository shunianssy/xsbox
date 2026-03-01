from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        # 1. 开启可视化模式，方便观察
        browser = p.chromium.launch(headless=False, slow_mo=500) 
        context = browser.new_context()
        page = context.new_page()

        try:
            # 2. 访问目标网址 (请替换为你实际的网址)
            url = "https://example.com/login" 
            print(f"正在访问：{url}")
            page.goto(url, wait_until="domcontentloaded")
            
            # 3. 截图查看加载后的状态
            page.screenshot(path="debug_loaded.png")
            print("页面加载完成，已截图 debug_loaded.png")

            # 4. 显式等待元素
            print("正在等待 #username 元素...")
            page.wait_for_selector("#username", state="visible", timeout=10000)
            
            # 5. 执行填充
            page.fill("#username", "test")
            print("填充成功！")
            
        except Exception as e:
            # 6. 报错时截图
            page.screenshot(path="debug_error.png")
            print(f"发生错误，已保存截图 debug_error.png")
            print(f"错误详情：{e}")
        finally:
            # 不要立即关闭，留 5 秒给你观察浏览器
            import time
            time.sleep(5)
            browser.close()

if __name__ == "__main__":
    run()