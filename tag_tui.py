import urwid
import json
import os
import sys
import logging
from datetime import datetime

DATA_FILE = 'data.json'
TAG_FILE = 'tagged_full_names.json'
LOG_DIR = 'logs'
EXPORT_FILE = 'tagged_repositories.md'

# 设置日志
def setup_logging():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    
    log_file = os.path.join(LOG_DIR, f'tag_app_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def load_full_names():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        full_names = []
        for category, items in data.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and 'full_name' in item:
                        # 同时加载 full_name, category, description 和 html_url
                        full_names.append({
                            'category': category,
                            'full_name': item['full_name'],
                            'description': item.get('description', '无描述'), # 获取 description，如果没有则显示"无描述"
                            'html_url': item.get('html_url', '') # 获取 html_url，如果没有则为空字符串
                        })
        logger.info(f"成功加载 {len(full_names)} 个仓库信息")
        return full_names
    except FileNotFoundError:
        logger.error(f"找不到数据文件 {DATA_FILE}")
        print(f"错误：找不到数据文件 {DATA_FILE}")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"{DATA_FILE} 文件格式不正确")
        print(f"错误：{DATA_FILE} 文件格式不正确")
        sys.exit(1)

def save_tags(tag_dict):
    try:
        with open(TAG_FILE, 'w', encoding='utf-8') as f:
            json.dump(tag_dict, f, ensure_ascii=False, indent=2)
        logger.info(f"成功保存标签到 {TAG_FILE}")
    except Exception as e:
        logger.error(f"保存标签时出错：{str(e)}")
        print(f"保存标签时出错：{str(e)}")

def load_tags():
    try:
        with open(TAG_FILE, 'r', encoding='utf-8') as f:
            tags = json.load(f)
        logger.info(f"成功加载现有标签从 {TAG_FILE}")
        return tags
    except FileNotFoundError:
        logger.info(f"找不到标签文件 {TAG_FILE}，将创建新的标签文件")
        return {}
    except json.JSONDecodeError:
        logger.error(f"标签文件 {TAG_FILE} 格式不正确")
        return {}
    except Exception as e:
        logger.error(f"加载标签时出错：{str(e)}")
        return {}

def export_markdown(tags, full_names):
    try:
        # 构建 full_name 到仓库信息的映射，方便查找
        repo_lookup = {item['full_name']: item for item in full_names}
        
        # 按标签分组仓库
        tags_to_repos = {}
        for full_name, tag_list in tags.items():
            if full_name in repo_lookup:
                repo_info = repo_lookup[full_name]
                for tag in tag_list:
                    if tag not in tags_to_repos:
                        tags_to_repos[tag] = []
                    tags_to_repos[tag].append(repo_info)
        
        with open(EXPORT_FILE, 'w', encoding='utf-8') as f:
            f.write("# Tagged Repositories\n\n")
            
            # 按标签名排序输出
            for tag in sorted(tags_to_repos.keys()):
                f.write(f"## {tag}\n")
                # 按 full_name 排序仓库
                for repo in sorted(tags_to_repos[tag], key=lambda x: x['full_name']):
                    description = repo.get('description', '无描述')
                    html_url = repo.get('html_url', '')
                    
                    if html_url:
                         f.write(f"- [{repo['full_name']}]({html_url}) - {description}\n")
                    else:
                         f.write(f"- {repo['full_name']} - {description}\n")
                f.write("\n")
        
        logger.info(f"成功导出 Markdown 到 {EXPORT_FILE}")
        return f"成功导出标签到 {EXPORT_FILE}"
        
    except Exception as e:
        logger.error(f"导出 Markdown 时出错：{str(e)}")
        return f"导出 Markdown 时出错：{str(e)}"

class TagApp:
    def __init__(self, full_names):
        self.full_names = full_names
        
        # 初始化标签字典，并尝试加载现有标签
        self.tags = {item['full_name']: [] for item in full_names}
        existing_tags = load_tags()
        # 合并现有标签，保留 load_full_names 中加载的 description 和 html_url
        for full_name, tag_list in existing_tags.items():
            if full_name in self.tags:
                self.tags[full_name] = tag_list

        self.current = 0
        # 更新主界面的输入提示
        self.edit = urwid.Edit(('editcp', u"输入标签(空格分隔): "))
        
        # 初始化视图模式
        self.view_mode = 'all' # 'all' 或 'untagged'
        
        # 更新使用说明，添加切换视图和导出 Markdown 的提示
        self.info = urwid.Text(u"使用说明：\n1. 使用上下键选择仓库\n2. 按回车键打开标签输入窗口\n3. 输入标签（用空格分隔）\n4. 点击确定保存\n5. 按 q 键保存并退出\n6. 按 m 键导出Markdown\n7. 使用左右键切换视图 (全部/未打标签)")
        
        # 根据当前视图模式创建列表
        self.listbox = urwid.ListBox(urwid.SimpleFocusListWalker(self.make_items(self.view_mode)))
        
        # 创建一个用于显示状态信息的文本组件
        self.status_text = urwid.Text(u"")
        
        self.frame = urwid.Frame(
            urwid.AttrWrap(self.listbox, 'body'),
            footer=urwid.Pile([self.info, self.edit, self.status_text]) # 将状态信息添加到 footer
        )
        logger.info("TagApp 初始化完成")

    def make_items(self, view_mode):
        items = []
        
        if view_mode == 'all':
            # 显示所有仓库，已打标签的仓库在最后有一个未打标签分类
            tagged_repos = []
            untagged_repos = []

            for item in self.full_names:
                full_name = item['full_name']
                tags_list = self.tags.get(full_name, []) 
                
                if tags_list:
                    tagged_repos.append((item, tags_list))
                else:
                    untagged_repos.append(item)

            # 添加已打标签的仓库
            for item, tags_list in tagged_repos:
                tag_str = ' '.join(tags_list)
                txt = f"[{item['category']}] {item['full_name']}  标签: {tag_str}"
                items.append(urwid.Text(txt))
                
            # 添加未打标签的仓库分类
            if untagged_repos:
                items.append(urwid.Divider())
                items.append(urwid.Text("--- 未打标签的仓库 ---"))
                items.append(urwid.Divider())
                for item in untagged_repos:
                     txt = f"[{item['category']}] {item['full_name']}  标签: 无"
                     items.append(urwid.Text(txt))
                     
        elif view_mode == 'untagged':
            # 只显示未打标签的仓库
            items.append(urwid.Text("--- 未打标签的仓库 ---"))
            items.append(urwid.Divider())
            has_untagged = False
            for item in self.full_names:
                full_name = item['full_name']
                tags_list = self.tags.get(full_name, [])
                if not tags_list:
                    txt = f"[{item['category']}] {item['full_name']}  标签: 无"
                    items.append(urwid.Text(txt))
                    has_untagged = True
            
            if not has_untagged:
                 items.append(urwid.Text("所有仓库都已打标签！"))

        return items

    def update_list(self):
        # 根据当前视图模式更新列表
        self.listbox.body[:] = self.make_items(self.view_mode)
        logger.debug(f"更新列表显示 - 视图模式: {self.view_mode}")

    def open_tag_popup(self, idx):
        full_name = self.full_names[idx]['full_name']
        description = self.full_names[idx].get('description', '无描述')
        current_tags = ' '.join(self.tags[full_name])
        logger.info(f"打开标签编辑窗口 - 仓库: {full_name}, 当前标签: {current_tags}")
        
        # 创建更清晰的输入界面
        header = urwid.Text(('header', f"为仓库 {full_name} 添加标签"))
        
        # 添加描述文本
        description_text = urwid.Text(f"描述: {description}")
        
        instruction = urwid.Text(('instruction', "请输入标签，多个标签用空格分隔\n例如: python web framework"))
        edit = urwid.Edit(('editcp', u"标签: "), current_tags)
        
        # 添加状态显示
        status = urwid.Text("")
        
        # 创建按钮
        ok_button = urwid.Button(('button', '确定'))
        cancel_button = urwid.Button(('button', '取消'))
        
        # 使用 Pile 垂直排列组件
        pile = urwid.Pile([
            ('pack', header),
            ('pack', urwid.Divider()),
            ('pack', description_text),
            ('pack', urwid.Divider()),
            ('pack', instruction),
            ('pack', urwid.Divider()),
            ('pack', edit),
            ('pack', urwid.Divider()),
            ('pack', status),
            ('pack', urwid.Divider()),
            ('pack', urwid.GridFlow([
                ok_button,
                cancel_button
            ], cell_width=15, h_sep=2, v_sep=1, align='center'))
        ])
        
        # 添加边框和填充
        box = urwid.LineBox(
            urwid.Padding(pile, left=2, right=2),
            title="标签编辑"
        )
        
        # 创建覆盖层
        overlay = urwid.Overlay(
            box,
            self.frame,
            align='center', width=('relative', 80),
            valign='middle', height=('relative', 60),
            min_width=40,
            min_height=20
        )
        
        def on_ok(button):
            tag_input = edit.edit_text.strip()
            if not tag_input:
                status.set_text(('error', "请输入至少一个标签"))
                return
                
            tags = [t.strip() for t in tag_input.split() if t.strip()]
            if not tags:
                status.set_text(('error', "请输入有效的标签"))
                return
                
            self.tags[full_name] = tags
            logger.info(f"更新标签 - 仓库: {full_name}, 新标签: {tags}")
            self.update_list()
            self.loop.widget = self.frame
            
        def on_cancel(button):
            logger.info(f"取消标签编辑 - 仓库: {full_name}")
            self.loop.widget = self.frame
            
        urwid.connect_signal(ok_button, 'click', on_ok)
        urwid.connect_signal(cancel_button, 'click', on_cancel)
        
        # 设置焦点到输入框
        self.loop.widget = overlay
        # 设置 pile 的焦点到编辑框
        pile.focus_position = 6  # edit 组件在 pile 中的位置

    def unhandled(self, key):
        if key in ('q', 'Q'):
            logger.info("用户退出程序")
            save_tags(self.tags)
            raise urwid.ExitMainLoop()
        elif key in ('m', 'M'):
            logger.info("用户请求导出 Markdown")
            # 调用导出函数并显示状态信息
            message = export_markdown(self.tags, self.full_names)
            self.status_text.set_text(message)
            logger.info(f"导出状态: {message}")
        elif key == 'left':
            # 切换到显示所有仓库模式
            if self.view_mode != 'all':
                self.view_mode = 'all'
                self.update_list()
                self.status_text.set_text(u"显示：所有仓库")
                logger.info("切换视图：所有仓库")
        elif key == 'right':
            # 切换到只显示未打标签仓库模式
            if self.view_mode != 'untagged':
                self.view_mode = 'untagged'
                self.update_list()
                self.status_text.set_text(u"显示：未打标签的仓库")
                logger.info("切换视图：未打标签的仓库")
        else:
            # 如果不是上述特殊按键，则调用原始的按键处理函数
            return key

    def main(self):
        try:
            loop = urwid.MainLoop(
                self.frame,
                palette=[
                    ('body', 'default', 'default'),
                    ('editcp', 'light cyan', 'default'),
                    ('focus', 'light red', 'default'),
                    ('header', 'light green', 'default'),
                    ('instruction', 'light gray', 'default'),
                    ('button', 'light blue', 'default'),
                    ('error', 'light red', 'default')
                ],
                unhandled_input=self.unhandled
            )
            self.loop = loop
            # 给 listbox 绑定 enter 事件
            orig_keypress = self.listbox.keypress
            def listbox_keypress(size, key):
                if key == 'enter':
                    idx = self.listbox.focus_position
                    self.open_tag_popup(idx)
                    return None
                return orig_keypress(size, key)
            self.listbox.keypress = listbox_keypress
            logger.info("开始运行主循环")
            loop.run()
        except Exception as e:
            logger.error(f"程序运行出错：{str(e)}")
            print(f"程序运行出错：{str(e)}")
            sys.exit(1)

if __name__ == '__main__':
    try:
        logger.info("程序启动")
        full_names = load_full_names()
        if not full_names:
            logger.error("没有找到任何仓库数据")
            print("错误：没有找到任何仓库数据")
            sys.exit(1)
        app = TagApp(full_names)
        app.main()
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        print("\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序出错：{str(e)}")
        print(f"程序出错：{str(e)}")
        sys.exit(1)
