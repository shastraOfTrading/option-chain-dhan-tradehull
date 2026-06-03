import numpy as np
import pandas as pd

def crsi(close, period=14, alpha=0.01):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(span=period, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(span=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)

    # Clean up before log
    rs = rs.replace([np.inf, -np.inf], np.nan).fillna(1)
    log_rs = np.log(rs).fillna(0)

    # Drift via EMA (memory), avoids exploding cumsum
    drift = log_rs.ewm(alpha=alpha, adjust=False).mean()
    return drift.fillna(0)




def supertrend(df, atr_period=15, atr_multiplier=3):

    print("Starting supertrend calculation.. Please wait..")

    if not 'TR' in df.columns:
        df['h-l'] = df['high'] - df['low']
        df['h-yc'] = abs(df['high'] - df['close'].shift())
        df['l-yc'] = abs(df['low'] - df['close'].shift())         
        df['TR'] = df[['h-l', 'h-yc', 'l-yc']].max(axis=1)
        df.drop(['h-l', 'h-yc', 'l-yc'], inplace=True, axis=1)

    # Compute ATR using exponential moving average
    atr = 'ATR_' + str(atr_period)
    df[atr] = df['TR'].ewm(alpha=1/atr_period, min_periods=atr_period).mean()
    
    st = 'ST_' + str(atr_period) + '_' + str(atr_multiplier)
    stx = 'STX_' + str(atr_period) + '_' + str(atr_multiplier)
    
    # Compute basic upper and lower bands
    df['basic_ub'] = (df['high'] + df['low']) / 2 + atr_multiplier * df[atr]
    df['basic_lb'] = (df['high'] + df['low']) / 2 - atr_multiplier * df[atr]

    # Compute final upper and lower bands
    df['final_ub'] = 0.00
    df['final_lb'] = 0.00
    for i in range(atr_period, len(df)):
        df.loc[df.index[i], 'final_ub'] = df['basic_ub'].iloc[i] if df['basic_ub'].iloc[i] < df['final_ub'].iloc[i - 1] or df['close'].iloc[i - 1] > df['final_ub'].iloc[i - 1] else df['final_ub'].iloc[i - 1]
        df.loc[df.index[i], 'final_lb'] = df['basic_lb'].iloc[i] if df['basic_lb'].iloc[i] > df['final_lb'].iloc[i - 1] or df['close'].iloc[i - 1] < df['final_lb'].iloc[i - 1] else df['final_lb'].iloc[i - 1]
       
    # Set the Supertrend value
    df[st] = 0.00
    for i in range(atr_period, len(df)):
        df.loc[df.index[i], st] = df['final_ub'].iloc[i] if df[st].iloc[i - 1] == df['final_ub'].iloc[i - 1] and df['close'].iloc[i] <= df['final_ub'].iloc[i] else \
                        df['final_lb'].iloc[i] if df[st].iloc[i - 1] == df['final_ub'].iloc[i - 1] and df['close'].iloc[i] >  df['final_ub'].iloc[i] else \
                        df['final_lb'].iloc[i] if df[st].iloc[i - 1] == df['final_lb'].iloc[i - 1] and df['close'].iloc[i] >= df['final_lb'].iloc[i] else \
                        df['final_ub'].iloc[i] if df[st].iloc[i - 1] == df['final_lb'].iloc[i - 1] and df['close'].iloc[i] <  df['final_lb'].iloc[i] else 0.00 
                 
    # Mark the trend direction up/down - Fix: Use object dtype to handle mixed types
    df[stx] = pd.Series(index=df.index, dtype='object')
    df.loc[df[st] > 0.00, stx] = np.where(df.loc[df[st] > 0.00, 'close'] < df.loc[df[st] > 0.00, st], 'down', 'up')
    df.loc[df[st] <= 0.00, stx] = None

    # Add the bands to your existing column names for compatibility
    df['upperband'] = df['final_ub']
    df['lowerband'] = df['final_lb']
    df['atr'] = df[atr]

    # Remove basic and final bands from the columns
    df.drop(['basic_ub', 'basic_lb', 'final_ub', 'final_lb', 'TR', atr], inplace=True, axis=1)
    
    df.fillna(0, inplace=True)

    print("Supertrend calculation completed..")

    return df

