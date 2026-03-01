@echo off
rem 切换到脚本所在目录 (使用 /d 参数以支持跨盘符切换)
cd /d "z:\academic\03-小巧思\gongwei"

rem 打印开始时间到日志
echo [%date% %time%] Starting essay update... >> run_log.txt

rem 使用绝对路径运行 Python 脚本，并将输出追加到日志文件
"C:\Users\luzey\AppData\Local\Programs\Python\Python312\python.exe" essayupdate.py >> run_log.txt 2>&1

echo [%date% %time%] Finished. >> run_log.txt
