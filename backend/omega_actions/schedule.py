"""Local 5-field cron matching for optional polling daemon, no cloud scheduler."""
from datetime import datetime

def field_matches(spec:str,value:int,minimum:int,maximum:int)->bool:
    for item in spec.split(','):
        step=1
        if '/' in item:
            item,raw_step=item.split('/',1)
            step=int(raw_step)
            if step<1: raise ValueError('Invalid cron step')
        if item=='*': lo,hi=minimum,maximum
        elif '-' in item:
            lo,hi=(int(x) for x in item.split('-',1))
        else:
            lo=hi=int(item)
            if '/' in spec and lo==hi: hi=maximum
        if lo<minimum or hi>maximum or lo>hi: raise ValueError('Cron field out of range')
        if lo<=value<=hi and (value-lo)%step==0: return True
    return False

def matches(cron:str,now:datetime)->bool:
    fields=cron.split()
    if len(fields)!=5: raise ValueError('Expected five cron fields')
    minute,hour,day,month,weekday=fields
    dow=(now.weekday()+1)%7
    day_match=field_matches(day,now.day,1,31)
    week_match=field_matches(weekday,dow,0,7) or (dow==0 and field_matches(weekday,7,0,7))
    # Vixie cron semantics: if both day-of-month and weekday restricted, OR them.
    if day!='*' and weekday!='*': calendar=day_match or week_match
    else: calendar=day_match and week_match
    return field_matches(minute,now.minute,0,59) and field_matches(hour,now.hour,0,23) and field_matches(month,now.month,1,12) and calendar
