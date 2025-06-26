import argparse
import json
import os
from datetime import datetime
from typing import Dict, List, Set
from pathlib import Path
from tabulate import tabulate
from colorama import init, Fore, Style
from scheduler import InstagramScheduler
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'instagram_scheduler_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

init(autoreset=True)  # colorama 초기화

class SchedulerCLI:
    def __init__(self):
        self.scheduler = InstagramScheduler()

    def _load_schedule(self) -> Dict:
        """스케줄 데이터 로드"""
        try:
            with open("schedules.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"{Fore.RED}스케줄 파일 로드 실패: {str(e)}")
            return {"schedules": [], "schedule_settings": {}}

    def _save_schedule(self, data: Dict):
        """스케줄 데이터 저장"""
        try:
            with open("schedules.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"{Fore.RED}스케줄 파일 저장 실패: {str(e)}")

    def list_schedules(self, username: str = None):
        """예약된 업로드 조회"""
        data = self._load_schedule()
        schedules = data["schedules"]

        if not schedules:
            print(f"{Fore.YELLOW}예약된 업로드가 없습니다.")
            return

        # 계정별로 스케줄 그룹화
        grouped_schedules = {}
        for schedule in schedules:
            if schedule["status"] == "completed":
                continue
            if username and schedule["username"] != username:
                continue
            if schedule["username"] not in grouped_schedules:
                grouped_schedules[schedule["username"]] = []
            grouped_schedules[schedule["username"]].append(schedule)

        if not grouped_schedules:
            print(f"{Fore.YELLOW}{'해당 계정의 ' if username else ''}대기 중인 예약이 없습니다.")
            return

        for account, account_schedules in grouped_schedules.items():
            print(f"\n{Fore.CYAN}=== {account} 계정의 예약된 업로드 ===")
            table_data = []
            for schedule in sorted(account_schedules, key=lambda x: x["scheduled_time"]):
                table_data.append([
                    schedule["video_name"],
                    schedule["scheduled_time"],
                    Fore.GREEN + "대기 중" + Style.RESET_ALL
                ])
            print(tabulate(table_data, headers=["영상", "예약 시간", "상태"], tablefmt="grid"))

    def delete_schedule(self, username: str = None, video_name: str = None):
        """예약 삭제"""
        data = self._load_schedule()
        original_count = len(data["schedules"])

        if username and video_name:
            # 특정 계정의 특정 영상 예약 삭제
            data["schedules"] = [
                s for s in data["schedules"]
                if not (s["username"] == username and s["video_name"] == video_name and s["status"] == "pending")
            ]
        elif username:
            # 특정 계정의 모든 예약 삭제
            data["schedules"] = [
                s for s in data["schedules"]
                if not (s["username"] == username and s["status"] == "pending")
            ]
        else:
            # 모든 대기 중인 예약 삭제
            data["schedules"] = [s for s in data["schedules"] if s["status"] != "pending"]

        deleted_count = original_count - len(data["schedules"])
        self._save_schedule(data)

        if deleted_count > 0:
            print(f"{Fore.GREEN}{deleted_count}개의 예약이 삭제되었습니다.")
        else:
            print(f"{Fore.YELLOW}삭제할 예약을 찾을 수 없습니다.")

    def find_unscheduled_videos(self, username: str = None):
        """예약되지 않은 영상 검색"""
        data = self._load_schedule()
        accounts = self.scheduler.accounts if not username else [
            acc for acc in self.scheduler.accounts if acc["username"] == username
        ]

        for account in accounts:
            videos_dir = os.path.join(account["account_directory"], "videos")
            if not os.path.exists(videos_dir):
                continue

            # 현재 예약된 영상들
            scheduled_videos = {
                s["video_name"] for s in data["schedules"]
                if s["username"] == account["username"] and s["status"] == "pending"
            }

            # 디렉토리의 모든 영상
            all_videos = {
                f for f in os.listdir(videos_dir)
                if f.endswith(('.mp4', '.mov', '.avi')) and not f.endswith('.uploaded')
            }

            # 예약되지 않은 영상 찾기
            unscheduled = all_videos - scheduled_videos

            if unscheduled:
                print(f"\n{Fore.CYAN}=== {account['username']} 계정의 예약되지 않은 영상 ===")
                for video in sorted(unscheduled):
                    print(f"{Fore.WHITE}• {video}")
            else:
                print(f"\n{Fore.YELLOW}{account['username']} 계정의 모든 영상이 예약되어 있습니다.")

    def find_missing_captions(self, username: str = None, find_orphaned: bool = False):
        """캡션이 없는 영상 또는 영상이 없는 캡션 검색"""
        accounts = self.scheduler.accounts if not username else [
            acc for acc in self.scheduler.accounts if acc["username"] == username
        ]

        for account in accounts:
            videos_dir = os.path.join(account["account_directory"], "videos")
            captions_dir = os.path.join(account["account_directory"], "captions")

            if not os.path.exists(videos_dir) or not os.path.exists(captions_dir):
                continue

            # 영상과 캡션 파일 목록
            videos = {
                os.path.splitext(f)[0] for f in os.listdir(videos_dir)
                if f.endswith(('.mp4', '.mov', '.avi')) and not f.endswith('.uploaded')
            }
            captions = {
                os.path.splitext(f)[0] for f in os.listdir(captions_dir)
                if f.endswith('.txt')
            }

            if not find_orphaned:
                # 캡션이 없는 영상 찾기
                missing_captions = videos - captions
                if missing_captions:
                    print(f"\n{Fore.CYAN}=== {account['username']} 계정의 캡션이 없는 영상 ===")
                    for video in sorted(missing_captions):
                        print(f"{Fore.WHITE}• {video}")
                else:
                    print(f"\n{Fore.GREEN}{account['username']} 계정의 모든 영상에 캡션이 있습니다.")
            else:
                # 영상이 없는 캡션 찾기
                orphaned_captions = captions - videos
                if orphaned_captions:
                    print(f"\n{Fore.CYAN}=== {account['username']} 계정의 영상이 없는 캡션 ===")
                    for caption in sorted(orphaned_captions):
                        print(f"{Fore.WHITE}• {caption}.txt")
                else:
                    print(f"\n{Fore.GREEN}{account['username']} 계정의 모든 캡션에 해당하는 영상이 있습니다.")

def load_config(config_path: str = "config.json") -> dict:
    """설정 파일 로드"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"설정 파일 로드 실패: {str(e)}")
        raise

def format_schedule_table(schedules: list) -> str:
    """스케줄 목록을 테이블 형식으로 포맷팅"""
    if not schedules:
        return "예약된 업로드가 없습니다."

    headers = ["ID", "계정", "비디오", "예약시간", "상태", "생성일시"]
    rows = []

    for schedule in schedules:
        video_name = os.path.basename(schedule["video_path"])
        rows.append([
            schedule["id"],
            schedule["account_username"],
            video_name,
            schedule["scheduled_time"],
            schedule["status"],
            schedule.get("created_at", "N/A")
        ])

    return tabulate(rows, headers=headers, tablefmt="grid")

def add_schedule(args, scheduler: InstagramScheduler, config: dict) -> None:
    """새로운 업로드 일정 추가"""
    try:
        # 계정 확인
        account = next(
            (acc for acc in config["accounts"] if acc["username"] == args.username),
            None
        )
        if not account:
            logger.error(f" 계정을 찾을 수 없습니다: {args.username}")
            return

        # 비디오 파일 경로 설정
        video_dir = os.path.join(account["account_directory"], config["directory_structure"]["videos_dir"])
        video_path = os.path.join(video_dir, args.video)

        if not os.path.exists(video_path):
            logger.error(f" 비디오 파일을 찾을 수 없습니다: {video_path}")
            return

        # 캡션 파일 확인 (옵션)
        caption = None
        if args.caption:
            caption_dir = os.path.join(account["account_directory"], config["directory_structure"]["captions_dir"])
            caption_path = os.path.join(caption_dir, f"{os.path.splitext(args.video)[0]}.txt")

            if os.path.exists(caption_path):
                with open(caption_path, 'r', encoding='utf-8') as f:
                    caption = f.read().strip()
            else:
                logger.warning(f" 캡션 파일을 찾을 수 없습니다: {caption_path}")
                tags = " ".join(account.get("default_tags", []))
                caption = f" {os.path.splitext(args.video)[0]}\n\n{tags}"

        # 스케줄 추가
        schedule = scheduler.add_schedule(
            account_username=args.username,
            video_path=video_path,
            scheduled_time=args.time,
            caption=caption
        )

        logger.info(" 새로운 업로드 일정이 추가되었습니다:")
        print(format_schedule_table([schedule]))

    except Exception as e:
        logger.error(f" 스케줄 추가 실패: {str(e)}")

def list_schedules(args, scheduler: InstagramScheduler) -> None:
    """업로드 일정 목록 조회"""
    try:
        schedules = scheduler.get_schedules(
            account_username=args.username,
            status=args.status
        )
        print(format_schedule_table(schedules))

    except Exception as e:
        logger.error(f" 스케줄 목록 조회 실패: {str(e)}")

def cancel_schedule(args, scheduler: InstagramScheduler) -> None:
    """업로드 일정 취소"""
    try:
        if scheduler.cancel_schedule(args.id):
            logger.info(f"업로드 일정이 취소되었습니다. (ID: {args.id})")
        else:
            logger.error(f" 일정 취소 실패 (ID: {args.id})")

    except Exception as e:
        logger.error(f" 스케줄 취소 실패: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Instagram 업로드 스케줄러 CLI")
    subparsers = parser.add_subparsers(dest="command", help="사용 가능한 명령어")

    # 스케줄 추가 명령어
    add_parser = subparsers.add_parser("add", help="새로운 업로드 일정 추가")
    add_parser.add_argument("username", help="Instagram 계정 사용자명")
    add_parser.add_argument("video", help="업로드할 비디오 파일명")
    add_parser.add_argument("time", help="예약 시간 (YYYY-MM-DD HH:MM 형식)")
    add_parser.add_argument("--caption", action="store_true", help="캡션 파일 사용 여부")

    # 스케줄 목록 조회 명령어
    list_parser = subparsers.add_parser("list", help="업로드 일정 목록 조회")
    list_parser.add_argument("--username", help="특정 계정의 일정만 조회")
    list_parser.add_argument("--status", choices=["pending", "completed", "failed", "cancelled"],
                            help="특정 상태의 일정만 조회")

    # 스케줄 취소 명령어
    cancel_parser = subparsers.add_parser("cancel", help="업로드 일정 취소")
    cancel_parser.add_argument("id", type=int, help="취소할 일정의 ID")

    args = parser.parse_args()

    try:
        config = load_config()
        scheduler = InstagramScheduler()

        if args.command == "add":
            add_schedule(args, scheduler, config)
        elif args.command == "list":
            list_schedules(args, scheduler)
        elif args.command == "cancel":
            cancel_schedule(args, scheduler)
        else:
            parser.print_help()

    except Exception as e:
        logger.error(f" CLI 실행 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    main()