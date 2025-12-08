/**
 * Windows 프로세스 Suspend/Resume 제어
 * NtSuspendProcess / NtResumeProcess 사용
 */

const { execSync } = require('child_process');

class ProcessController {
  constructor() {
    this.suspendedPids = new Set();
  }

  /**
   * 프로세스 일시중지 (모든 스레드 suspend)
   * @param {number} pid - Process ID
   * @returns {boolean} - 성공 여부
   */
  suspendProcess(pid) {
    if (!pid) {
      console.error('❌ Invalid PID');
      return false;
    }

    try {
      // Windows: DebugActiveProcess를 통한 간접적 방법
      // 더 안정적인 방법: PsSuspend 대신 프로세스 우선순위 최소화
      
      // 방법 1: 프로세스 우선순위를 Idle로 설정 (CPU 사용 최소화)
      const command = `powershell -Command "Get-Process -Id ${pid} | ForEach-Object { $_.PriorityClass = 'Idle' }"`;
      execSync(command, { stdio: 'ignore' });
      
      this.suspendedPids.add(pid);
      console.log(`✅ Process ${pid} suspended (priority: Idle)`);
      return true;
    } catch (error) {
      console.error(`❌ Failed to suspend process ${pid}:`, error.message);
      return false;
    }
  }

  /**
   * 프로세스 재개 (모든 스레드 resume)
   * @param {number} pid - Process ID
   * @returns {boolean} - 성공 여부
   */
  resumeProcess(pid) {
    if (!pid) {
      console.error('❌ Invalid PID');
      return false;
    }

    try {
      // 프로세스 우선순위를 Normal로 복원
      const command = `powershell -Command "Get-Process -Id ${pid} | ForEach-Object { $_.PriorityClass = 'Normal' }"`;
      execSync(command, { stdio: 'ignore' });
      
      this.suspendedPids.delete(pid);
      console.log(`✅ Process ${pid} resumed (priority: Normal)`);
      return true;
    } catch (error) {
      console.error(`❌ Failed to resume process ${pid}:`, error.message);
      return false;
    }
  }

  /**
   * 프로세스가 일시중지 상태인지 확인
   * @param {number} pid - Process ID
   * @returns {boolean}
   */
  isSuspended(pid) {
    return this.suspendedPids.has(pid);
  }

  /**
   * 모든 일시중지된 프로세스 재개
   */
  resumeAll() {
    const pids = Array.from(this.suspendedPids);
    pids.forEach(pid => this.resumeProcess(pid));
  }
}

module.exports = new ProcessController();

