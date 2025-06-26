import json
import logging
from datetime import datetime
from pathlib import Path
import os
from typing import Dict, List, Optional
import pytz

class InstagramScheduler:
    def __init__(self, config_path: str = "config.json"):
        """스케줄러 초기화"""
        self.config = self._load_config(config_path)
        self.schedule_file = self.config["scheduler_settings"]["schedules_file"]
        self.schedules = self._load_schedules()
        self.timezone = pytz.timezone(self.config["scheduler_settings"]["timezone"])

        # 로그 디렉토리 설정
        log_dir = self.config["directory_structure"]["logs_dir"]
        os.makedirs(log_dir, exist_ok=True)

        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(
                    log_dir,
                    f'instagram_scheduler_{datetime.now().strftime("%Y%m%d")}.log'
                )),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _load_config(self, config_path: str) -> Dict:
        """설정 파일 로드"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise Exception(f"설정 파일 로드 실패: {str(e)}")

    def _load_schedules(self) -> Dict:
        """스케줄 파일 로드"""
        if os.path.exists(self.schedule_file):
            try:
                with open(self.schedule_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.error("스케줄 파일이 손상되었습니다. 새로운 스케줄 파일을 생성합니다.")
                return {"schedules": []}
        return {"schedules": []}

    def _save_schedules(self) -> None:
        """스케줄 파일 저장"""
        with open(self.schedule_file, 'w', encoding='utf-8') as f:
            json.dump(self.schedules, f, ensure_ascii=False, indent=2)

    def add_schedule(self, account_username: str, video_path: str,
                    scheduled_time: str, caption: Optional[str] = None) -> Dict:
        """새로운 업로드 일정 추가"""
        try:
            # 시간 형식 검증
            scheduled_datetime = datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M")

            # 현재 시간보다 이전인지 확인
            current_time = datetime.now(self.timezone)
            if scheduled_datetime.replace(tzinfo=self.timezone) <= current_time:
                raise ValueError("예약 시간은 현재 시간보다 이후여야 합니다.")

            schedule = {
                "id": len(self.schedules["schedules"]) + 1,
                "account_username": account_username,
                "video_path": video_path,
                "caption": caption,
                "scheduled_time": scheduled_time,
                "status": "pending",
                "created_at": current_time.strftime("%Y-%m-%d %H:%M:%S")
            }

            self.schedules["schedules"].append(schedule)
            self._save_schedules()
            self.logger.info(f" 새로운 업로드 일정이 추가되었습니다. (ID: {schedule['id']})")
            return schedule

        except ValueError as e:
            self.logger.error(f" 일정 추가 실패: {str(e)}")
            raise

    def get_schedules(self, account_username: Optional[str] = None,
                     status: Optional[str] = None) -> List[Dict]:
        """업로드 일정 조회"""
        schedules = self.schedules["schedules"]

        if account_username:
            schedules = [s for s in schedules if s["account_username"] == account_username]
        if status:
            schedules = [s for s in schedules if s["status"] == status]

        return sorted(schedules, key=lambda x: x["scheduled_time"])

    def cancel_schedule(self, schedule_id: int) -> bool:
        """업로드 일정 취소"""
        for schedule in self.schedules["schedules"]:
            if schedule["id"] == schedule_id:
                if schedule["status"] == "pending":
                    schedule["status"] = "cancelled"
                    self._save_schedules()
                    self.logger.info(f" 업로드 일정이 취소되었습니다. (ID: {schedule_id})")
                    return True
                else:
                    self.logger.warning(f" 이미 처리된 일정은 취소할 수 없습니다. (ID: {schedule_id})")
                    return False

        self.logger.error(f" 일정을 찾을 수 없습니다. (ID: {schedule_id})")
        return False

    def get_pending_uploads(self) -> List[Dict]:
        """현재 시간에 업로드해야 할 일정 조회"""
        current_time = datetime.now(self.timezone)
        pending_uploads = []

        for schedule in self.schedules["schedules"]:
            if schedule["status"] != "pending":
                continue

            scheduled_time = datetime.strptime(
                schedule["scheduled_time"],
                "%Y-%m-%d %H:%M"
            ).replace(tzinfo=self.timezone)

            if scheduled_time <= current_time:
                pending_uploads.append(schedule)

        return pending_uploads

    def mark_schedule_completed(self, schedule_id: int) -> None:
        """업로드 완료 처리"""
        for schedule in self.schedules["schedules"]:
            if schedule["id"] == schedule_id:
                schedule["status"] = "completed"
                schedule["completed_at"] = datetime.now(self.timezone).strftime("%Y-%m-%d %H:%M:%S")
                self._save_schedules()
                self.logger.info(f" 업로드 완료 처리되었습니다. (ID: {schedule_id})")
                return

        self.logger.error(f" 일정을 찾을 수 없습니다. (ID: {schedule_id})")

    def mark_schedule_failed(self, schedule_id: int, error_message: str) -> None:
        """업로드 실패 처리"""
        for schedule in self.schedules["schedules"]:
            if schedule["id"] == schedule_id:
                schedule["status"] = "failed"
                schedule["error_message"] = error_message
                schedule["failed_at"] = datetime.now(self.timezone).strftime("%Y-%m-%d %H:%M:%S")
                self._save_schedules()
                self.logger.info(f" 업로드 실패 처리되었습니다. (ID: {schedule_id})")
                return

        self.logger.error(f" 일정을 찾을 수 없습니다. (ID: {schedule_id})")