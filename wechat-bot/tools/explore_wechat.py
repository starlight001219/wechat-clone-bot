"""探索微信 4.x UI 结构"""
import uiautomation as auto

wx = auto.WindowControl(searchDepth=1, ClassName='Qt51514QWindowIcon', Name='微信')
if not wx.Exists(0, 0):
    print('未找到微信，请先打开微信并登录')
    exit()

print('=== 微信控件树 (深度遍历) ===')
def walk(node, depth=0):
    if depth > 6:
        return
    try:
        name = (node.Name or '')[:80]
        cn = node.ClassName or ''
        rect = node.BoundingRectangle
        ctrl_type = node.ControlTypeName or ''
        prefix = '  ' * depth

        # 只打印有意义的节点
        if name or cn:
            is_visible = rect.right > rect.left and rect.bottom > rect.top
            if is_visible:
                print(f'{prefix}[{ctrl_type}][{cn}] \"{name}\"')

        children = node.GetChildren()
        for child in children:
            walk(child, depth+1)
    except Exception as e:
        print(f'  {"  "*depth}<{e}>')

walk(wx)
