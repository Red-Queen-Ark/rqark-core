import subprocess
import threading

from rqark_core.prompts.git_project import GitProjectPrompt

GIT_CONFIG = ('-c', 'user.name=Test', '-c', 'user.email=test@example.com')


def make_repo(path):
    subprocess.run(['git', 'init', '-q', '-b', 'main', str(path)], check=True)
    (path / 'tracked.txt').write_text('hello\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(path), *GIT_CONFIG, 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(path), *GIT_CONFIG, 'commit', '-q', '-m', 'first commit'], check=True)


async def test_git_prompt_reports_the_repository_state(tmp_path):
    make_repo(tmp_path)
    (tmp_path / 'untracked.txt').write_text('x', encoding='utf-8')

    text = await GitProjectPrompt(tmp_path).get_messages()

    assert text is not None
    assert 'Current branch: main' in text
    assert 'HEAD: ' in text
    assert 'untracked.txt' in text
    assert 'first commit' in text


async def test_git_prompt_is_absent_outside_a_repository(tmp_path):
    assert await GitProjectPrompt(tmp_path).get_messages() is None


async def test_git_commands_run_off_the_event_loop(tmp_path, monkeypatch):
    make_repo(tmp_path)
    loop_thread = threading.get_ident()
    threads = []
    real_run = subprocess.run

    def record(*args, **kwargs):
        threads.append(threading.get_ident())
        return real_run(*args, **kwargs)

    monkeypatch.setattr('rqark_core.prompts.git_project.subprocess.run', record)

    await GitProjectPrompt(tmp_path).get_messages()

    assert len(threads) == 4
    assert all(thread is not loop_thread for thread in threads)

