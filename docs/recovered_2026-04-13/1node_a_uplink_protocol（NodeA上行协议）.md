# Node A ��������Э��˵��

���ĵ����ڹ̶���ǰ `Node A` �Ĵ��������ʽ�����������ʽ�����ݽ����ǵ�ǰ�������Ѿ�ʵ�ֵĲ��֡�

## ���÷�Χ

- ��ǰ���أ�ESP32-S3
- ��ǰ�ڵ��ţ�`A1`
- ��ǰ�ڵ��ɫ��`EDGE`
- ��ǰ���ͨ����USB ���ڼ�����
- ��ǰ�����ʣ�`115200`

## ��ǰ֧�ֵ���������

��������ͨ�� USB ���ڷ��͸� ESP32��ÿ�������һ�У����س�������

### HELP

���ܣ�
- ��ӡ��ǰ֧�ֵ������б���

ʾ����

```text
HELP
```

### STATUS

���ܣ�
- �����ǰϵͳ״̬���ա�

ʾ����

```text
STATUS
```

����ʾ����

```text
STATUS,node=A1,hunter=IDLE,gimbal=SCANNING,rid=UNKNOWN,risk=0.0,track=0,active=0,confirmed=0,x=0.0,y=0.0,test_mode=0,servo_enabled=1,manual_pan=90.0,manual_tilt=90.0,safe_mode=0,diag_running=0,debug=1,uplink=1
```

### SELFTEST

���ܣ�
- �����ǰ�����Լ�ժҪ��
- �����ڲ����״������̨ʱ����ȷ��������ؼ�״̬��

ʾ����

```text
SELFTEST
```

����ʾ����

```text
SELFTEST,BEGIN
SELFTEST,node=A1,role=EDGE
SELFTEST,monitor_baud=115200,radar_baud=256000
SELFTEST,hunter=IDLE,gimbal=SCANNING,rid=UNKNOWN,risk=0.0
SELFTEST,track=0,active=0,confirmed=0,x=0.0,y=0.0,vx=0.0,vy=0.0
SELFTEST,sim_enabled=0,sim_active=0,sim_x=0.0,sim_y=0.0,sim_hold_ms=1500
SELFTEST,test_mode=0,servo_enabled=1,servo_attached=1,manual_pan=90.0,manual_tilt=90.0,safe_mode=0,diag_running=0,debug=1,uplink=1
SELFTEST,predictor_kp=0.450,predictor_kd=0.050
SELFTEST,heartbeat_ms=1000,event_report_ms=250
SELFTEST,idle_ready=1
SELFTEST,END
```

### DEBUG,ON

���ܣ�
- �򿪱��ص��������
- �������� `GIMBAL / DATA / STATE`��

### DEBUG,OFF

���ܣ�
- �رձ��ص��������
- �رպ������ `GIMBAL / DATA / STATE`���� `UPLINK,HB / UPLINK,TRACK / UPLINK,EVENT` ��Ȼ������

˵����
- ������ˢ��̫�졢Ӱ����������ʱ������ʹ�� `DEBUG,OFF`��

### UPLINK,ON

���ܣ�
- �� `UPLINK,HB / UPLINK,TRACK / UPLINK,EVENT` �����

### UPLINK,OFF

���ܣ�
- �ر� `UPLINK,HB / UPLINK,TRACK / UPLINK,EVENT` �����

˵����
- ����ֻ����Զ��������뿴�κ�����ˢ��ʱ��ʹ�� `UPLINK,OFF`��
- `RESET` ���ָ�Ϊ `UPLINK,ON`��

### SAFE,ON

���ܣ�
- �򿪱��ذ�ȫ�Ƕ����ơ�
- �򿪺��ֶ����������ʹ�ø�С�İ�ȫ�Ƕȷ�Χ��

### SAFE,OFF

���ܣ�
- �رձ��ذ�ȫ�Ƕ����ơ�
- �رպ󣬻ָ���ǰĬ�ϽǶ����ơ�

### DIAG,SERVO

���ܣ�
- �����������������̡�
- ������Զ��� `SAFE,ON`��`SERVO,ON`��`TESTMODE,ON`��
- Ȼ�󰴡�����λ��С��С�ҡ�С�ϡ�С�¡������ġ���˳���Զ����ԡ�

˵����
- �����̲��ܶ�ȡ�����ʵ�����������ÿһ����Ŀ��ǶȺ͹۲���ʾֱ�Ӵ�ӡ������
- ����κ�һ�����־��Ҷ�����Ӧ�������� `DIAG,STOP` �� `SERVO,OFF`��

### DIAG,STOP

���ܣ�
- ����ֹͣ��ǰ�������������̡�
- �����Զ��ָ��Զ�����������ָ�������ʹ�� `TESTMODE,OFF`��

### TESTMODE,ON

���ܣ�
- ����̨�ֶ�����ģʽ��
- �򿪺󣬶������ɴ����ֶ�����ӹܣ����ٸ����Զ����������

ʾ����

```text
TESTMODE,ON
```

### TESTMODE,OFF

���ܣ�
- �ر���̨�ֶ�����ģʽ��
- �رպ�ϵͳ�ָ���ǰ�Զ��������ơ�

### SERVO,ON

���ܣ�
- ʹ�ܶ�� PWM �����
- �ʺ���ȷ�Ϲ���ͻ�е״̬���ٴ򿪶����

### SERVO,OFF

���ܣ�
- �رն�� PWM �����
- �ʺ��ڽ��ߡ��ϵ�ǰ�����Ҷ�ʱ����ͣ�����

### CENTER

���ܣ�
- ���ֶ�����Ŀ��Ƕ��û�����λ��
- ��ǰ����λ���� `CenterPanDeg` �� `CenterTiltDeg`��

### PAN,value

���ܣ�
- �����ֶ�����ģʽ�µ�ˮƽĿ��Ƕȡ�
- �ǶȻᱻ�����ڵ�ǰ��ȫ��Χ�ڡ�

ʾ����

```text
PAN,60
```

### TILT,value

���ܣ�
- �����ֶ�����ģʽ�µĸ���Ŀ��Ƕȡ�
- �ǶȻᱻ�����ڵ�ǰ��ȫ��Χ�ڡ�

ʾ����

```text
TILT,100
```

### TRACK,x,y

���ܣ�
- ע��ģ��켣���꣬�����ʵ�״����롣
- �ʺ������״������¼����ƽ� `TrackManager -> HunterAction -> GimbalController -> UPLINK` ������

ʾ����

```text
TRACK,320,1800
```

����ʾ����

```text
Simulation track updated: x=320.0,y=1800.0
```

˵����
- һ��ע���ϵͳ���ڶ�ʱ���ڳ������øõ㣬ֱ����ʱ�������
- ������������Ҳ�����ù켣����ȷ�����̡�

### TRACK,CLEAR

���ܣ�
- �����ǰģ��켣��

ʾ����

```text
TRACK,CLEAR
```

����ʾ����

```text
Simulation track cleared.
```

### RID,OK

���ܣ�
- ����ǰ RID ״̬��Ϊ `MATCHED`��

### RID,MISSING

���ܣ�
- ����ǰ RID ״̬��Ϊ `MISSING`��

### RID,SUSPICIOUS

���ܣ�
- ����ǰ RID ״̬��Ϊ `SUSPICIOUS`��

### KP,value

���ܣ�
- ��̬�޸�Ԥ��������ʱ `Kp` ������

ʾ����

```text
KP,0.60
```

### KD,value

���ܣ�
- ��̬�޸�Ԥ��������ʱ `Kd` ������

ʾ����

```text
KD,0.10
```

### RESET

���ܣ�
- �� `rid_status` �ָ�Ϊ `UNKNOWN`
- ���ģ��켣
- �� `Kp` �� `Kd` �ָ�ΪĬ��ֵ

ʾ����

```text
RESET
```

## ���ڵ������

### GIMBAL

���ܣ�
- �����̨��ǰ״̬��Ŀ��켣ժҪ��

ʾ����

```text
GIMBAL,SCANNING,test_mode=0,servo_enabled=1,track_active=0,confirmed=0,x=0.0,y=0.0,vx=0.0,vy=0.0
```

˵����
- ��ǰ���ص������������Ƶ�����ٰ�ÿ������ѭ������ˢ����
- ��ǰ `GIMBAL`��`STATUS`��`SELFTEST` �л������ `safe_mode` �� `diag_running`������ȷ�ϵ�ǰ�Ƿ��ڱ���/���״̬��

### DATA

���ܣ�
- �������λ����ͼʹ�õļ����ݡ�

ʾ����

```text
DATA,1500.0,92.5
```

˵����
- �� 1 �У�Ŀ�� `x_mm`
- �� 2 �У���ǰ `pan_angle`

### STATE

���ܣ�
- ��� Hunter ��ǰ״̬����շ�����

ʾ����

```text
STATE,SUSPICIOUS,57.0
```

## UPLINK,HB

���ܣ�
- ����֡
- �����������ǰ�ڵ�����״̬

������ڣ�
- `CloudConfig::HeartbeatMs`

ʾ����

```text
UPLINK,HB,node=A1,role=EDGE,ts=12345,hunter=IDLE,gimbal=SCANNING,rid=UNKNOWN,risk=0.0,alert=0,capture=0,guardian=0
```

## SUMMARY 扩展�?2026-04-01

### SUMMARY

功能�?
- 输出当前弢�机以来的联调摘要统计�?
- 适合在真实雷达或模拟轨迹跑一轮后，快速看主链是否真正走过�?

示例�?
```text
SUMMARY
```

返回示例�?
```text
SUMMARY,node=A1,uptime_ms=24567,track_active=2,track_confirmed=1,track_lost=1,gimbal_tracking=1,gimbal_lost=1,hunter_changes=3,max_risk=57.0,last_track=4,last_x=320.0,last_y=1800.0,last_event_id=A1-0000023456-0001
```

字段含义�?
- `track_active`：本次开机以来进�?`active=1` 的次数��?
- `track_confirmed`：本次开机以来进�?`confirmed=1` 的次数��?
- `track_lost`：本次开机以来目标丢失的次数�?
- `gimbal_tracking` / `gimbal_lost`：云台切�?`TRACKING / LOST` 的次数��?
- `hunter_changes`：\unter 状��切换次数��?
- `max_risk`：本次开机以来的朢�高风险分�?
- `last_track` / `last_x` / `last_y`：最近一次有效目标的 ID 和坐标��?
- `last_event_id`：最近一次联动事件的事件编号，如果还没有则为 `NONE`�?

### SUMMARY,RESET

功能�?
- 清空当前 `SUMMARY` 统计，从此刻重新弢�始计数��?

示例�?
```text
SUMMARY,RESET
```

## ZONE ��չ��2026-04-01

��ǰ�ڵ��������̶��ֶ� `zone`�����ڱ�ʾ�ڵ���������/������

��ǰĬ��ֵ��

```text
ZONE_NORTH
```

��ǰ���λ�ã�

- `STATUS`
- `SELFTEST`
- `SUMMARY`
- `UPLINK,HB`
- `UPLINK,TRACK`
- `UPLINK,EVENT`

ʾ����

```text
UPLINK,HB,node=A1,zone=ZONE_NORTH,role=EDGE,ts=12345,hunter=IDLE,gimbal=SCANNING,rid=UNKNOWN,risk=0.0,alert=0,capture=0,guardian=0
```

�ֶ�˵����

- `node`���ڵ���
- `role`���ڵ��ɫ
- `ts`��ϵͳ���к���ʱ���
- `hunter`��Hunter ״̬
- `gimbal`����̨״̬
- `rid`��RID ״̬
- `risk`����ǰ���շ���
- `alert`���Ƿ񴥷����ظ澯
- `capture`���Ƿ񴥷�ץ�Ķ���
- `guardian`���Ƿ񴥷������ն˱�����·

## UPLINK,TRACK

���ܣ�
- �켣֡
- �����ڻ�ԾĿ��ʱ������������켣��Ϣ

���������
- `snapshot.radar_track.is_active == true`

������ڣ�
- `CloudConfig::EventReportMs`

ʾ����

```text
UPLINK,TRACK,node=A1,ts=12600,track=3,active=1,confirmed=1,x=320.0,y=1800.0,vx=40.0,vy=-10.0,seen=12,lost=0
```

�ֶ�˵����

- `track`���켣���
- `active`���켣��ǰ�Ƿ��Ծ
- `confirmed`���켣�Ƿ���ȷ��
- `x / y`����ǰ����
- `vx / vy`���ٶȹ���
- `seen`�������۲����
- `lost`����ʧ����

## UPLINK,EVENT

���ܣ�
- �¼�֡
- ���ؼ�״̬�����仯ʱ�������

��ǰ `reason` ���ͣ�

- `TRACK_CHANGED`����Ŀ���ˣ�
- `TRACK_ACTIVE`��������Ŀ��
- `TRACK_LOST`��Ŀ�������/����ʧ��
- `HUNTER_STATE`�����֣���в�ȼ�����/������
- `RID_STATE`�����ݣ�����������

ʾ����

```text
UPLINK,EVENT,node=A1,ts=12700,reason=TRACK_ACTIVE,track=3,hunter=SUSPICIOUS,gimbal=TRACKING,rid=MISSING,risk=63.0,alert=1,capture=1,guardian=0,x=320.0,y=1800.0
```

## ��ǰ״̬ö��

### Hunter ״̬

- `IDLE`:���� / ����
- `TRACKING`:׷���� / ���־���
- `RID_MATCHED`:�Ѿ����� / �������
- `SUSPICIOUS`:����Ŀ�� / ��ɫ����
- `HIGH_RISK`:��Σ / ��ɫ���վ���
- `EVENT_LOCKED`���¼����� / ��װ�����ʼ��

### ��̨״̬

- `SCANNING`
- `ACQUIRING`
- `TRACKING`
- `LOST`

### RID ״̬

- `UNKNOWN`
- `MATCHED`
- `MISSING`��ȱʧ / �ڷ�
- `SUSPICIOUS`������ / ����

## ˵��

- ��ǰЭ���Ǵ������ȵĵ����������ø�ʽ��
- ��ǰ�Ѿ�֧��ģ��켣ע�룬��������״�������Ҳ�ܿ��� `UPLINK,TRACK` ������¼������
- ������������ƶ˻�˫�ڵ�������Ӧ���Ȼ��ڱ��ĵ�������չ������������һ��������
