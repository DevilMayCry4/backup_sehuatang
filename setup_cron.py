import os
from crontab import CronTab

def setup_backup_cron():
    current_dir = os.getcwd()
    script_path = os.path.join(current_dir, "mongo_backup.py")
    
    # 获取当前用户的crontab
    cron = CronTab(user=True)

    # 删除已存在的备份任务
    cron.remove_all(comment='mongodb_backup')

    # 创建新的备份任务（每天凌晨2点执行）
    command = f'cd {current_dir} && /usr/bin/python3 {script_path}'
    job = cron.new(command=command, comment='mongodb_backup')
    job.hour.on(2)
    job.minute.on(0)

    # 写入crontab
    cron.write()
    print("Backup cron job has been set up successfully!")

if __name__ == '__main__':
    setup_backup_cron()