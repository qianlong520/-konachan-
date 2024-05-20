import os
import re
import requests
import shutil
from PIL import Image
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3 import Retry
import time


def is_valid_url(url):
    try:
        # 使用urlparse函数对URL进行解析
        result = urlparse(url)
        # 如果URL的scheme和netloc都存在，那么这是一个有效的URL
        return all([result.scheme, result.netloc])
    except ValueError:
        # 如果URL解析过程中出现值错误，说明这不是一个有效的URL
        return False


def create_session():
    # 创建一个requests的Session对象
    session = requests.Session()
    # 设置重试次数和重试间隔，
    retries = Retry(total=5, backoff_factor=0.1,
                    status_forcelist=[500, 502, 503, 504])

    # 为http和https协议设置重试策略
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session


def scrape_wallpaper_url(url):
    try:
        print(f'正在获取壁纸网址： {url}...')
        # 定义请求头，模拟用户浏览器行为
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
        # 使用之前创建的会话发起GET请求
        session = create_session()
        response = session.get(url, headers=headers)
        # 使用BeautifulSoup解析网页内容
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup
    except Exception as e:
        print(f"获取壁纸网址时发生异常: {e}")
        return None


def parse_wallpaper_url(soup):
    if soup is None:
        # 如果页面内容为空，返回空列表
        return [], [], []

    post_list = soup.find('ul', {'id': 'post-list-posts'})
    wallpaper_urls = []
    li_content = []
    li_id_and_url = []
    li_tags = []

    if post_list is not None:
        # 找出所有的li标签，并提取文本内容
        li_tags = post_list.find_all('li')
        li_content = [li.text for li in li_tags]

        for li in li_tags:
            a_tags = li.find_all('a')

            for a_tag in a_tags:
                if 'href' in a_tag.attrs and is_valid_url(a_tag['href']):
                    # 使用正则表达式匹配jpg图片链接
                    match = re.match(r'(.*\.jpg)$', a_tag['href'], re.IGNORECASE)
                    if match:
                        # 如果匹配成功，把结果加入到壁纸链接列表中
                        wallpaper_urls.append(match.group(0))
                        li_id_and_url.append({'id': li.get('id'), 'url': match.group(0)})

        while len(wallpaper_urls) != len(li_tags):
            print(f"当前壁纸链接数: {len(wallpaper_urls)}, 期待的数量: {len(li_tags)}")

    print(f"最终壁纸链接数: {len(wallpaper_urls)}, 期待的数量: {len(li_tags)}")
    print(f"li_id_and_url: {li_id_and_url}")
    return wallpaper_urls, li_content, li_id_and_url


def save_image_to_folder(id_url_dict, folder_name, image_number):
    url = id_url_dict['url']
    image_id = id_url_dict['id']
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
    session = create_session()
    max_retries = 10   #重试10次
    for attempt in range(max_retries):
        print(f"开始下载图片 {image_id}")
        try:
            response = session.get(url, stream=True, headers=headers, timeout=10)
            if response.status_code != 200:
                raise ValueError(f"服务器响应代码: {response.status_code}")
            response.raw.decode_content = True
            filename = f"{image_id}.jpg"
            with open(os.path.join(folder_name, filename), 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            print(f"成功将图片 {image_id} 保存到文件夹： {folder_name}...")
            return  # 图像保存成功后中断循环
        except (requests.exceptions.RequestException, requests.exceptions.Timeout, ValueError) as e:
            print(f"下载图片 {image_id} 失败，错误信息： {str(e)}，正在尝试第 {attempt + 1} 次重试...")
            time.sleep(1)  # 在重试之间增加等待时间
            if attempt == (max_retries - 1):
                print(f"下载图片 {image_id} 失败，已达到最大重试次数 {max_retries}...")
                break





def scrape_and_save(page_url):
    try:
        max_page_retries = 10  # 定义最大页面重试次数
        max_image_retries = 10  # 定义最大图片重试次数
        for page_attempt in range(max_page_retries):
            soup = scrape_wallpaper_url(page_url)
            if soup is None:
                if page_attempt == (max_page_retries - 1):
                    # 如果页面内容获取失败，则输出错误信息
                    print(f"无法获取页面: {page_url} 的内容，尽管已经尝试了 {max_page_retries} 次。")
                    return
                print(f"无法获取页面: {page_url} 的内容，现在尝试重新获取...")
                time.sleep(1)  # 每次重试之间暂停1秒
                continue

            wallpaper_urls, li_contents, li_id_and_urls = parse_wallpaper_url(soup)
            print(f"在页面 {page_url} 中找到 {len(wallpaper_urls)} 张图片")
            folder_name = 'Wallpapers'
            if not os.path.exists(folder_name):
                os.makedirs(folder_name)  # 如果指定文件夹不存在，则创建该文件夹
            # 根据壁纸数量设置线程数。
            with ThreadPoolExecutor(max_workers=len(wallpaper_urls)) as executor:
                for index, id_url_dict in enumerate(li_id_and_urls):
                    executor.submit(save_image_with_retries, id_url_dict, folder_name, index + 1, max_image_retries)
            break  # 如果成功获取页面内容，跳出循环
    except Exception as e:
        print(f"抓取和保存图片时出现错误: {e}")


def save_image_with_retries(id_url_dict, folder_name, image_number, max_image_retries):
    for image_attempt in range(max_image_retries):
        try:
            save_image_to_folder(id_url_dict, folder_name, image_number)
            break
        except Exception as e:
            print("在保存图片时出现错误，现在尝试重新下载...")
            if image_attempt == (max_image_retries - 1):
                print(f"尽管尝试了 {max_image_retries} 次，图片仍未能成功下载。现在跳过该图片...")
                break

def create_folder_path(folder_name, parent_directory):
    try:
        # 创建一个新的文件夹路径
        folder_path = os.path.join(parent_directory, folder_name)
        if not os.path.exists(folder_path):
            # 如果文件夹不存在，创建一个新的文件夹
            os.makedirs(folder_path)
        return folder_path
    except Exception as e:
        print(f"创建文件夹路径时发生异常: {e}")
        return None


def organize_images():
    try:
        # 定义分类比例和分类对应的名字
        ratio_folders = {
            "3比2": (3, 2),
            "4比3": (4, 3),
            "1比1": (1, 1),
            "16比9": (16, 9),
            "3比1": (3, 1),
            "不匹配": (0, 0)
        }
        # 定义分辨率范围和分类对应的名字
        resolution_folders = {
            "540p以下": 540,
            "540p到1080p": 1080,
            "1080p到2k": 2048,
            "2k到3k": 3072,
            "3k到4k": 4096,
            "4k到5k": 5120,
            "5k到6k": 6144,
            "6k到7k": 7168,
            "7k到8k": 8192,
            "8k以上": float('inf'),
            "不匹配": 0
        }
        # 创建分类文件夹
        organized_folder = create_folder_path('Organized_files', '.')
        resolution_folder = create_folder_path('按分辨率分类', organized_folder)
        ratio_folder = create_folder_path('按长宽比分类', organized_folder)

        # 在分类文件夹下创建对应的子文件夹
        for folder in ratio_folders.keys():
            create_folder_path(folder, ratio_folder)

        for folder in resolution_folders.keys():
            create_folder_path(folder, resolution_folder)

        # 遍历所有图片文件
        for img in os.listdir('./Wallpapers'):
            if img.endswith(".jpg") or img.endswith('.jpeg') or img.endswith('.JPG') or img.endswith('.JPEG'):
                img_path = os.path.join('./Wallpapers', img)
                try:
                    with Image.open(img_path) as im:
                        # 获取图片宽高，计算比例
                        width, height = im.size

                        if height == 0:
                            ratio = 0
                        else:
                            ratio = width / height

                        is_match = False
                        # 根据比例选择对应的文件夹
                        for folder, ratio_value in ratio_folders.items():
                            # 判断是否在比例范围内
                            if abs(ratio - ratio_value[0] / ratio_value[1]) < 0.2:
                                is_match = True
                                dest_folder = create_folder_path(folder, ratio_folder)
                                # 复制文件到指定文件夹
                                shutil.copy2(img_path, dest_folder)
                                print(f'复制 {img} 到 {dest_folder}')
                                break

                        # 如果没有匹配的比例，复制到不匹配文件夹
                        if not is_match:
                            dest_folder = create_folder_path("不匹配", ratio_folder)
                            shutil.copy2(img_path, dest_folder)
                            print(f'复制 {img} 到 {dest_folder}')

                        # 根据高度选择对应的文件夹
                        resolution = height
                        is_match = False
                        for folder, res_value in resolution_folders.items():
                            # 判断是否在高度范围内
                            if height <= res_value:
                                is_match = True
                                dest_folder = create_folder_path(folder, resolution_folder)
                                shutil.copy2(img_path, dest_folder)
                                print(f'复制 {img} 到 {dest_folder}')
                                break

                        # 如果没有匹配的高度，复制到不匹配文件夹
                        if not is_match:
                            dest_folder = create_folder_path("不匹配", resolution_folder)
                            shutil.copy2(img_path, dest_folder)
                            print(f'复制 {img} 到 {dest_folder}')
                except IOError:
                    print(f'无法识别的图像文件: {img}')
    except Exception as e:
        print(f"在组织图像时发生异常: {e}")


def create_and_copy_images():
    try:
        print("开始创建和复制图像...")  # 打印开始创建和复制图像的信息
        folder_name = "Rename_format"  # 定义目标文件夹的名称为"Rename_format"
        original_folder = "Wallpapers"  # 定义源文件夹的名称为"Wallpapers"
        if not os.path.exists(folder_name):  # 如果目标文件夹不存在
            os.makedirs(folder_name)  # 则创建目标文件夹
        img_files = os.listdir(original_folder)  # 获取源文件夹中的所有文件名
        img_files = [img for img in img_files if img.endswith(".jpg")]  # 过滤出所有.jpg文件
        for img in img_files:  # 遍历所有.jpg文件
            shutil.copy2(os.path.join(original_folder, img), os.path.join(folder_name, img))  # 将每个.jpg文件从源文件夹复制到目标文件夹
        renamed_count = 1  # 初始化重命名计数器为1
        for img in os.listdir(folder_name):  # 遍历目标文件夹中的所有文件
            if img.endswith(".jpg"):  # 如果是.jpg文件
                new_name = str(renamed_count) + ".jpg"  # 生成新的文件名，格式为"{计数器}.jpg"
                os.rename(os.path.join(folder_name, img), os.path.join(folder_name, new_name))  # 将文件重命名
                renamed_count += 1  # 计数器加1
        print("完成创建和复制图像.")  # 打印完成创建和复制图像的信息
    except Exception as e:  # 捕获所有异常
        print(f"创建和复制图像时出现异常: {e}")  # 打印出现异常的信息


def create_url_list(page_count):
    try:
        print('正在创建网址列表...')
        # 创建要爬取的网页URL列表
        return [f"https://konachan.net/post?page={i}&tags=" for i in range(1, page_count + 1)]
    except Exception as e:
        print(f"创建网址列表时出现异常: {e}")
        return []


def get_maximum_page_number():
    try:
        print('正在获取最大页数...')
        # 设置请求头模拟浏览器
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
        # 创建请求会话
        session = create_session()
        # 发送请求获取内容
        response = session.get("https://konachan.net/post?page=1&tags=", headers=headers)
        # 使用BeautifulSoup解析html内容
        soup = BeautifulSoup(response.text, 'html.parser')
        # 找到存储页码的div元素
        pagination_div = soup.find('div', {'class': 'pagination'})

        if pagination_div:
            # 获取最后一页的URL
            last_page_link = pagination_div.find_all('a')[-2]['href']
            # 获取URL中的页码部分
            index = last_page_link.find("page=")
            page_number = last_page_link[index + 5:].split('&')[0]
            print(f'最大页数为： {int(page_number)}')
            return int(page_number)
        else:
            print("未找到分页元素")
            return 0
    except Exception as e:
        print(f"获取最大页数时发生异常: {e}")
        return 0


from concurrent.futures import ThreadPoolExecutor


def main():
    try:
        # 打印开始运行程序的信息
        print("开始运行程序...")
        # 获取最大页码数量
        # page_count = get_maximum_page_number()
        #
        page_count = 100
        # 创建网页URL列表
        page_urls = create_url_list(page_count)
        # 检查爬取文件的目录是否存在，如果不存在则创建对应目录
        if not os.path.exists('./Wallpapers'):
            os.makedirs('./Wallpapers')

        # 使用 ThreadPoolExecutor 进行多线程下载和保存图片
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(scrape_and_save, page_urls)

        # 打印程序运行结束的信息
        print("程序运行结束.")

        # 对图片进行组织和分类
        organize_images()

        # 在其他操作完成后调用创建和复制图像的函数
        create_and_copy_images()

    except Exception as e:
        # 打印出现的错误信息
        print(f"发生意外错误: {e}")


# 如果直接运行此脚本，则会运行main函数
if __name__ == "__main__":
    main()
