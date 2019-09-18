# DarkGuardian(黑暗守卫)
DarkGuardian是一款用于监控RDP登录后TSCLIENT(挂盘)的工具,工具后台运行时可自动获取挂盘的文件列表,下载指定文件,拷贝木马文件到挂载硬盘的启动项等功能
# 优点
* 后台运行,无需实时干预
* 支持下载指定文件及正则匹配等多种模式
* 可通过拷贝木马方式攻击维护人员个人PC
* 通过暗影使用时,支持维护人员挂载硬盘短信提醒(出网/不出网皆适配)
# 缺点
* 可执行文件大(7M)
# 使用方法
Windows Vista 及以上版本
* 将main.exe,config.json上传到已控制主机
* 后台运行main.exe(蚁剑命令行直接运行即可)

Windows Vista 以下版本
* 将可执行文件main.exe,start.vbs,config.json上传到已控制主机
* rdp远程登录服务器,命令行运行start.vbs
## 配置文件说明
```
{
  "download_file_list": [
   "\\\\tsclient\\C\\Users\\funnywolf\\Desktop\\dic_username_svn.txt",
    "\\\\tsclient\\C\\Users\\funnywolf\\Desktop\\dic_password_svn.txt"
  ],//需要下载的文件列表
  "download_file_regex_list": [
    "服务器",
    "项目",
    "密码",
    "配置",
    "网站",
    "手册",
    "方案"
  ],//需要下载的文件名正则表达式列表re.search
  "file_suffix_whitelist": [
    "cer",
    "csv",
    "db",
    "doc",
    "docx",
    "pdf",
    "pem",
    "ppt",
    "pptx",
    "rtf",
    "txt",
    "xls",
    "xlsx"
  ],//获取文件目录时的后缀白名单
  "file_suffix_blacklist": [
    "iso"
  ],//获取文件目录时的后缀黑名单
  "download_file_maxsize": 10485760,//下载文件的最大大小 10*1024*1024字节
  "upload_file_list": [
    "shellloader.zip"
  ]//需要解压到启动项挂载C盘启动项的压缩包(放在可执行文件相同目录下)
}
```
# 已测试
* Windows server 2003
* Windows Server 2012
# 工具截图
![图片](https://uploader.shimo.im/f/hhfWvzfm8jwg79kX.png!thumbnail)

![图片](https://uploader.shimo.im/f/Hf2gdC7RnDY7jn7H.png!thumbnail)
# 更新日志
**1.0 beta**
更新时间: 2019-09-18
* 发布1.0试用版

